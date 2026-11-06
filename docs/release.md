# Release (owner steps)

Nothing is published until the owner does the last step by hand. Claude never creates certificates, adds secrets
or pushes tags (SPEC §4.23, ADR-0010).

## Once: the project's signing certificate (owner)

1. On **your own Mac, not the floor test Mac**: Keychain Access → Certificate Assistant → **Create a Certificate…**
   Name e.g. `DT3 Agent Code Signing`, Identity Type **Self-Signed Root**, Certificate Type **Code Signing**.
2. Export it with its private key as `.p12` and a strong password. **Back up the .p12 and the password** (offline):
   losing the key means every user has to grant the DEVONthink permission again (ADR-0010).
3. GitHub → repository → Settings → Secrets and variables → Actions → three **repository secrets**:

| Secret | Value |
|---|---|
| `RELEASE_CERT_P12` | the .p12 file as base64: `base64 -i cert.p12 \| pbcopy` |
| `RELEASE_CERT_PASSWORD` | the .p12 password |
| `RELEASE_CERT_NAME` | the certificate name, e.g. `DT3 Agent Code Signing` |

## Test build on the floor Mac (no certificate)

```bash
tools/release.sh 0.0.1 x86_64
```

Builds `build/DT3-Agent-0.0.1-Intel-NOT-FOR-RELEASE.dmg` (ad-hoc signed) for the release test (`docs/test-plan.md`).
Use the version that is currently in the code.

## Releasing (owner, after the release test passed)

1. A PR sets the version to `1.0.0` in `engine/dt3agent/__init__.py`, `app/Agent/Info.plist`,
   `app/EngineHost/Info.plist` and moves the CHANGELOG section from "Unreleased" to "1.0.0 – date".
2. After that PR is merged, the owner tags `main`:

```bash
git tag -a v1.0.0 -m "DT3 Agent 1.0.0" && git push origin v1.0.0
```

3. The `release` workflow builds `DT3-Agent-1.0.0-Intel.dmg` and `DT3-Agent-1.0.0-AppleSilicon.dmg`, signs them
   with the certificate and creates a **draft** release. It stops if the certificate secrets are missing.
4. Owner: download both DMGs from the draft, install one on a clean Mac, then press **Publish release**.

UNVERIFIED until the first tag: trusting the self-signed certificate on the GitHub runner, and the x86_64
llama-server cross-built on an Apple Silicon runner.
