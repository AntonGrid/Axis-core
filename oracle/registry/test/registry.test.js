const assert = require('assert');
const { spawn } = require('child_process');
const path = require('path');
const crypto = require('crypto');
const fetch = require('node-fetch');
const nacl = require('tweetnacl');
const util = require('tweetnacl-util');

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function sha256(data) {
  return crypto.createHash('sha256').update(data).digest();
}

/**
 * Verify a Merkle proof exactly like the ENRG on-chain verifier
 * (`compute_merkle_root` in merkle_proof_verification.rs):
 * position bit 0 -> hash(current, sibling); bit 1 -> hash(sibling, current).
 */
function verifyMerkleProof(leafHex, proofHexes, position, rootHex) {
  let current = Buffer.from(leafHex, 'hex');
  let pos = position;
  for (const s of proofHexes) {
    const sibling = Buffer.from(s, 'hex');
    current =
      pos % 2 === 0
        ? sha256(Buffer.concat([current, sibling]))
        : sha256(Buffer.concat([sibling, current]));
    pos = Math.floor(pos / 2);
  }
  return current.toString('hex') === rootHex;
}

describe('Manifest Registry API', function () {
  this.timeout(20000);
  let server;

  const BASE = 'http://127.0.0.1:4101';

  before(async function () {
    server = spawn('node', ['server.js'], {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env, PORT: '4101', REGISTRY_ADMIN_KEY: 'test-key' },
      stdio: ['ignore', 'pipe', 'pipe']
    });

    server.stdout.on('data', (chunk) => process.stdout.write(chunk));
    server.stderr.on('data', (chunk) => process.stdout.write(chunk));

    await wait(1000);
  });

  after(() => {
    if (server) {
      server.kill('SIGTERM');
    }
  });

  async function publishManifest(manifestId, payload) {
    const keyPair = nacl.sign.keyPair();
    const signature = util.encodeBase64(
      nacl.sign.detached(Buffer.from(JSON.stringify(payload)), keyPair.secretKey)
    );
    const publicKey = util.encodeBase64(keyPair.publicKey);

    const res = await fetch(`${BASE}/api/v1/manifests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ manifest_id: manifestId, payload, signature, public_key: publicKey })
    });
    return res;
  }

  it('publishes and retrieves a manifest', async function () {
    const payload = { manifest_version: '1.0', device_type: 'sensor', manufacturer: 'Axis' };
    const res = await publishManifest('manifest-test-01', payload);
    assert.strictEqual(res.status, 201);
    const published = await res.json();
    assert.strictEqual(published.status, 'published');

    const getRes = await fetch(`${BASE}/api/v1/manifests/manifest-test-01`);
    assert.strictEqual(getRes.status, 200);
    const data = await getRes.json();
    assert.strictEqual(data.payload.manifest_version, '1.0');
  });

  it('rejects a manifest_id that is not exactly 16 bytes', async function () {
    const payload = { manifest_version: '1.0', device_type: 'sensor' };
    // 15 bytes — incompatible with on-chain manifest_id([u8; 16]).
    const res = await publishManifest('manifest-test-1', payload);
    assert.strictEqual(res.status, 400);
  });

  it('creates a snapshot, exposes current root and serves a verifiable Merkle proof', async function () {
    const ids = ['manifest-test-aa', 'manifest-test-bb', 'manifest-test-cc'];
    for (const id of ids) {
      const res = await publishManifest(id, { manifest_version: '1.0', device_type: 'sensor', manifest_id: id });
      assert.strictEqual(res.status, 201);
    }

    const snapshotRes = await fetch(`${BASE}/api/v1/merkle/snapshot`, {
      method: 'POST',
      headers: { 'x-api-key': 'test-key' }
    });
    assert.strictEqual(snapshotRes.status, 201);
    const snapshot = await snapshotRes.json();
    assert.ok(snapshot.root);
    // The registry state is shared across tests in this file, so the snapshot
    // contains every manifest published so far (>= the three published here).
    assert.ok(snapshot.total >= 3);

    const currentRes = await fetch(`${BASE}/api/v1/merkle/current`);
    assert.strictEqual(currentRes.status, 200);
    const current = await currentRes.json();
    assert.strictEqual(current.root, snapshot.root);

    // Proof for the middle leaf.
    const proofRes = await fetch(`${BASE}/api/v1/merkle/proof/manifest-test-bb`);
    assert.strictEqual(proofRes.status, 200);
    const proof = await proofRes.json();
    assert.strictEqual(proof.root, snapshot.root);
    assert.ok(Array.isArray(proof.proof));
    assert.ok(proof.proof.length >= 1);
    assert.strictEqual(typeof proof.position, 'number');

    // Recompute the root from the leaf + proof — must match.
    assert.strictEqual(
      verifyMerkleProof(proof.leaf, proof.proof, proof.position, snapshot.root),
      true
    );
  });

  it('returns 404 for a proof of an unknown manifest', async function () {
    const res = await fetch(`${BASE}/api/v1/merkle/proof/does-not-exist-01`);
    assert.strictEqual(res.status, 404);
  });
});

