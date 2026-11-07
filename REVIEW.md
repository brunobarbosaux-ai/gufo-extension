# Review policy

A release enters the registry only after a Gufo maintainer reviews its source
at the listed commit and approves the pull request. The approval is the record
of the review. Keep the pull request discussion focused on that commit.

## Author checklist

Copy into the pull request description:

```markdown
- [ ] Release: <name> <version> at <full commit>
- [ ] Source license (SPDX):
- [ ] Model weight licenses and how users obtain the weights:
- [ ] Maintainers listed in the entry agree to be contacted about it
- [ ] Builds with `gufo extension install <source>@<commit>` on: <platforms, gufo revision>
- [ ] Evidence: conformance results, quality report and benchmark settings, or a link to them in the extension repository
- [ ] Changes since the previous release (for an update): <compare link>
```

## Reviewer checklist

The reviewer reads the whole diff since the previous reviewed release (the
whole tree for a new extension) and confirms:

- **No code beyond the stated purpose.** Nothing reaches the network,
  launches processes, reads or writes files outside the model, cache and the
  user's explicit paths, collects telemetry, or hides behavior. CMake runs at
  install time with the user's permissions: check `extension.cmake` and every
  file it includes.
- **No prebuilt binaries or downloads.** No vendored object files, libraries,
  generated blobs or build-time downloads that the review cannot read.
  Third-party sources are pinned and their licenses noted.
- **Public surface only.** Only `<gufo/ext/...>` headers and the public
  `gufo_ext_*` link targets, so the extension builds as a module. Every
  library it includes is declared (`packages`, imported targets); headers
  that happen to be on the include path don't count.
- **Truthful metadata.** `extension.json` providers, capabilities, keys and
  model IDs describe what the code serves; no claim on IDs owned by another
  extension.
- **License.** A source license that allows redistribution and use. Model
  weights are not bundled without the right to do so.
- **Accountability.** Listed maintainers are reachable.

`tools/registry.py verify` covers the mechanical checks: the commit exists
at `source`, the manifest fields match, and the digest matches. It does not
replace reading the code.

## Withdrawal

A release with a security or license problem is removed in its own pull
request that explains why. Users who installed it see that in the registry
history; gufo will warn about installed releases that are no longer listed.
