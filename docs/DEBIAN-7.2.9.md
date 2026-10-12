# Debian 7.2.9 build target

Recorded October 12, 2026. **Experimental: build validation only.** The
historical `SOURCE.json` and its limited 7.2.8 hardware evidence are preserved.
`SOURCE-7.2.9.json` adds Debian source package `7.2.9-1` and target kernel
`7.2.9+deb14-amd64`. All 41 checked driver source/header hashes match the
historical baseline; no textual patch rebase was needed.

## Source and headers

Obtain `linux-source-7.2` version `7.2.9-1` using authenticated Debian package
tools. Compare its package SHA-256 against `SOURCE-7.2.9.json`, then extract
the package and its source archive as described in
[BUILD-AND-ROLLBACK.md](BUILD-AND-ROLLBACK.md).

On a Debian installation providing this release, install matching headers and
BTF tooling, for example:

```sh
sudo apt install linux-headers-7.2.9+deb14-amd64 pahole
```

The headers require their matching common-header and kbuild packages. APT
normally resolves these dependencies. Verify package versions and generated
kernel release; the helper's checks do not authenticate header downloads.
Privately extracted headers are also supported with the paths described in the
build document.

## Build

From the repository root:

```sh
sha256sum -c SHA256SUMS
python3 scripts/build.py \
  --source /path/to/linux-source-7.2 \
  --kdir /lib/modules/7.2.9+deb14-amd64/build \
  --manifest SOURCE-7.2.9.json \
  --variant queue-only
```

Choose a fresh `--output` if the default directory already exists. The explicit
manifest retains source hashes, allowed source paths, matching kernel release,
nonempty symbol table, and output separation checks. Omitting `--manifest`
continues to select the 7.2.8 baseline. Manifests are reviewed local inputs,
not independent trust anchors; do not edit hashes merely to bypass a mismatch.

## Evidence and limits

- Queue-only (0001 + 0002) compiled and linked against matching installed Debian
  7.2.9 headers with GCC 16.2, `W=1`, and BTF using pahole 1.32. No compiler
  warnings or errors were observed.
- Both patch series applied with zero fuzz to the matching 7.2.9 source.
  Queue-and-sync has **not been compiled for 7.2.9**.
- The build helper recorded manifest, patch, symbol-table, and module hashes in
  `build-info.json`. Helper tests exercise explicit manifest selection and
  rejection of modified source and mismatched headers.
- No 7.2.9 experimental module was loaded during this validation. Client
  reconnection, sleep/wake, multicast, throughput, recovery, sustained use, and
  two-client stability remain pending.

## Secure Boot and temporary testing

Use the distribution's supported module signing and MOK enrollment procedure
when Secure Boot requires it. Keep private signing keys outside this repository.
An expected `modinfo` signer does not prove that the kernel trusts the key.
On the tested system, `mokutil --test-key` returned exit status zero even for
an unenrolled certificate; inspect its enrollment result before a test load.

Keep Secure Boot enabled, preserve the stock signed module, and follow
[temporary load and rollback](BUILD-AND-ROLLBACK.md#temporary-load) with wired
or console recovery access. Reboot restores stock modules only when there is
no persistent DKMS, initramfs, or modprobe override. Binaries, private keys,
private logs, credentials, and local network configuration are not published.
