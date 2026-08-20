const app = require('./app');
const PORT = process.env.PORT || 4000;

// Fail-fast: the registry requires an admin key to create Merkle snapshots.
// Running without it would silently leave the snapshot endpoint unusable.
if (!process.env.REGISTRY_ADMIN_KEY) {
  console.error(
    'REGISTRY_ADMIN_KEY is required: set it to start the Manifest Registry ' +
      '(see oracle/registry/README.md).'
  );
  process.exit(1);
}

app.listen(PORT, () => {
  console.log(`Manifest Registry running on port ${PORT}`);
});
