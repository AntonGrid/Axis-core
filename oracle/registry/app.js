const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const crypto = require('crypto');
const nacl = require('tweetnacl');
const util = require('tweetnacl-util');
const { v4: uuidv4 } = require('uuid');

const app = express();
app.use(cors());
app.use(bodyParser.json());

const PORT = process.env.PORT || 4000;
const ADMIN_KEY = process.env.REGISTRY_ADMIN_KEY;
const SERVICE_NAME = process.env.SERVICE_NAME || 'axis-manifest-registry';

const manifests = new Map();
const snapshots = [];

function verifySignature(payload, signature, publicKey) {
  try {
    const msg = Buffer.from(JSON.stringify(payload));
    const sig = util.decodeBase64(signature);
    const pub = util.decodeBase64(publicKey);
    return nacl.sign.detached.verify(msg, sig, pub);
  } catch (e) {
    return false;
  }
}

function canonicalize(data) {
  return typeof data === 'string' ? data : JSON.stringify(data);
}

// ── SHA-256 Merkle — bit-compatible with the ENRG on-chain verifier
//    (merkle_proof_verification.rs) and ENRG tests/helpers/merkle.ts:
//    leaf = SHA-256(manifest_id(16) || content_hash(32))
//    node = SHA-256(left(32) || right(32))   (single hash)
//    Odd levels duplicate the last node. The leaf index is the position;
//    proof siblings alternate left/right based on the position bits. ──

function sha256(data) {
  return crypto.createHash('sha256').update(data).digest();
}

function merkleHash(left, right) {
  return sha256(Buffer.concat([left, right]));
}

/** Deterministic manifest content hash: SHA-256 of the canonical payload. */
function contentHashOf(payload) {
  return sha256(Buffer.from(canonicalize(payload)));
}

/** leaf = SHA-256(manifest_id(16 bytes) || content_hash(32 bytes)). */
function manifestLeaf(manifestId, contentHash) {
  return sha256(Buffer.concat([Buffer.from(manifestId, 'utf8'), contentHash]));
}

/**
 * Build a Merkle tree from 32-byte raw leaf hashes (NOT re-hashed — matches
 * on-chain `compute_merkle_root`). Returns { levels, root }.
 */
function buildMerkleTree(rawLeaves) {
  const leaves = rawLeaves;
  const levels = [leaves];
  let level = leaves;
  while (level.length > 1) {
    const next = [];
    for (let i = 0; i < level.length; i += 2) {
      next.push(merkleHash(level[i], level[i + 1] || level[i]));
    }
    levels.push(next);
    level = next;
  }
  return { levels, root: levels[levels.length - 1][0] };
}

/** Sibling path for the leaf at `index` (mirror of ENRG tests/helpers/merkle.ts). */
function getProof(tree, index) {
  const proof = [];
  let idx = index;
  for (let li = 0; li < tree.levels.length - 1; li++) {
    const level = tree.levels[li];
    const sibling = idx % 2 === 1 ? idx - 1 : idx + 1;
    proof.push(sibling < level.length ? level[sibling] : level[idx]);
    idx = Math.floor(idx / 2);
  }
  return proof;
}

function createSnapshot() {
  const ids = Array.from(manifests.keys());
  const leaves = ids.map((id) => {
    const entry = manifests.get(id);
    return manifestLeaf(id, contentHashOf(entry.payload));
  });
  const tree = buildMerkleTree(leaves);
  const snapshot = {
    id: uuidv4(),
    root: tree.root.toString('hex'),
    total: ids.length,
    timestamp: new Date().toISOString(),
    // Leaves are kept so proofs stay valid even if manifests are added
    // after this snapshot was created.
    leaves: leaves.map((l) => l.toString('hex')),
  };
  snapshots.push(snapshot);
  return snapshot;
}

function findSnapshotWithLeaf(manifestId) {
  const entry = manifests.get(manifestId);
  if (!entry) return null;
  const leafHex = manifestLeaf(
    manifestId,
    contentHashOf(entry.payload)
  ).toString('hex');
  // Prefer the most recent snapshot that contains this leaf.
  for (let i = snapshots.length - 1; i >= 0; i--) {
    const snap = snapshots[i];
    const index = snap.leaves.indexOf(leafHex);
    if (index !== -1) {
      return { snapshot: snap, leafHex, index };
    }
  }
  return null;
}


app.get('/health', (req, res) => {
  res.json({ ok: true, service: SERVICE_NAME, manifests: manifests.size, snapshots: snapshots.length });
});

app.post('/api/v1/manifests', (req, res) => {
  const { manifest_id, payload, signature, public_key } = req.body;
  if (!manifest_id || !payload || !signature || !public_key) {
    return res.status(400).json({ error: 'Missing fields' });
  }

  // On-chain compatibility requires a 16-byte manifest id
  // (see merkle_proof_verification.rs: manifest_id([u8; 16])).
  if (Buffer.byteLength(String(manifest_id), 'utf8') !== 16) {
    return res.status(400).json({ error: 'manifest_id must be exactly 16 bytes' });
  }

  if (!verifySignature(payload, signature, public_key)) {
    return res.status(400).json({ error: 'Invalid signature' });
  }

  manifests.set(manifest_id, { payload, signature, public_key, created_at: new Date().toISOString() });
  res.status(201).json({ manifest_id, status: 'published' });
});

app.get('/api/v1/manifests/:id', (req, res) => {
  const entry = manifests.get(req.params.id);
  if (!entry) return res.status(404).json({ error: 'Not found' });
  res.json(entry);
});

app.post('/api/v1/merkle/snapshot', (req, res) => {
  if (req.headers['x-api-key'] !== ADMIN_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  if (manifests.size === 0) {
    return res.status(400).json({ error: 'No manifests to snapshot' });
  }

  const snapshot = createSnapshot();
  res.status(201).json(snapshot);
});

app.get('/api/v1/merkle/current', (req, res) => {
  if (snapshots.length === 0) {
    return res.json({ root: null, message: 'No snapshots yet' });
  }
  const s = snapshots[snapshots.length - 1];
  res.json({ id: s.id, root: s.root, total: s.total, timestamp: s.timestamp });
});

app.get('/api/v1/merkle/proof/:manifestId', (req, res) => {
  const { manifestId } = req.params;
  if (!manifests.has(manifestId)) {
    return res.status(404).json({ error: 'Manifest not found' });
  }

  const found = findSnapshotWithLeaf(manifestId);
  if (!found) {
    return res.status(404).json({ error: 'No snapshot contains this manifest' });
  }

  const { snapshot, leafHex, index } = found;
  const leaves = snapshot.leaves.map((hex) => Buffer.from(hex, 'hex'));
  const tree = buildMerkleTree(leaves);
  const proof = getProof(tree, index).map((h) => h.toString('hex'));

  res.json({
    manifest_id: manifestId,
    root: snapshot.root,
    leaf: leafHex,
    position: index,
    proof,
  });
});

app.get('/api/v1/manifests', (req, res) => {
  res.json(Array.from(manifests.entries()).map(([manifest_id, entry]) => ({ manifest_id, ...entry })));
});

if (require.main === module) {
  if (!ADMIN_KEY) {
    console.error(
      'REGISTRY_ADMIN_KEY is required: set it to start the Manifest Registry ' +
        '(see oracle/registry/README.md).'
    );
    process.exit(1);
  }
  app.listen(PORT, () => {
    console.log(`${SERVICE_NAME} running on port ${PORT}`);
  });
}

module.exports = app;
