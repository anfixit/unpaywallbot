# Optional account storage

The authenticated browser component is disabled in the default bot runtime.
This storage is intended only for controlled research with an account that
the operator is authorized to use. It is not a credential-sharing service.

## Security model

Account records contain an email, password, optional session cookies, domain,
and Telegram user ID. The complete file is encrypted before it is written.

The current format provides:

- a versioned JSON envelope
- Fernet authenticated encryption
- PBKDF2-HMAC-SHA256 key derivation
- a fresh random salt for every write
- atomic temporary-file replacement
- file mode `0600`
- strict validation when loading
- backward decryption of the legacy Fernet token format

A damaged file or a wrong `ENCRYPTION_KEY` causes startup to fail closed.
The manager never silently replaces unreadable storage with an empty file.

## Add an account

Do not put a password in a command argument. Interactive use reads it with
`getpass`, so it is not visible in shell history or the process list:

```bash
uv run python -m scripts.register_accounts \
  --domain example.com \
  --email user@example.com \
  --user-id 123456789
```

For non-interactive automation, pass one line through standard input:

```bash
printf '%s\n' "$ACCOUNT_PASSWORD" | \
  uv run python -m scripts.register_accounts \
  --domain example.com \
  --email user@example.com \
  --user-id 123456789 \
  --password-stdin
```

The default file is `data/sessions/accounts.json`. The directory is ignored
by Git. A different location can be selected with `--storage`.

## Legacy migration

Old storage is decrypted with the legacy fixed-salt KDF. The next successful
write automatically stores it in the current salted envelope and adds the
internal file-format version.

Before migration:

1. stop every process that can write the file
2. create an encrypted backup
3. confirm the current `ENCRYPTION_KEY`
4. run one account update
5. verify that the account can be loaded again

## Operational limitations

- Use one writer process for a storage file. In-process writes are serialized,
  but the file is not a distributed database.
- Keep the storage outside backups that are available to untrusted users.
- Rotate credentials according to the publisher account policy.
- Delete the record when it is no longer required.
- Never commit the storage, passwords, cookies, or decrypted exports.
- Keep this component disabled when public-only extraction is sufficient.
