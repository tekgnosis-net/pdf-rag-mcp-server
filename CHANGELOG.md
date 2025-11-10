## [1.7.1](https://github.com/tekgnosis-net/pdf-rag-mcp-server/compare/v1.7.0...v1.7.1) (2025-11-10)


### Bug Fixes

* align vite proxy with backend port ([33671c0](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/33671c0cf0c4341a13178f66144c594863fcd507))
* **ci:** allow release workflow on main and master ([e53bd9d](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/e53bd9d8af4afd26f8df662f4873507351c5135a))

# [1.7.0](https://github.com/tekgnosis-net/pdf-rag-mcp-server/compare/v1.6.0...v1.7.0) (2025-11-10)


### Features

* surface client connection telemetry ([1554366](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/15543663dd19a1b94accc2b0fd113256b7b945df))

# [1.6.0](https://github.com/tekgnosis-net/pdf-rag-mcp-server/compare/v1.5.1...v1.6.0) (2025-11-09)


### Bug Fixes

* **vector-store:** resolve lance persistence path ([d4c96a5](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/d4c96a57bc3c0d13bc8c063773f9ab28e043c0ec))
* **vector-store:** resolve lance persistence path ([c5e6883](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/c5e688321072a32f1ffa1f238ef0271af2a19c0e))


### Features

* defer reparse cleanup ([0b7f1d2](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/0b7f1d2608392dd0c30e504ee2d969b05381620a))
* enhance reparse controls and image handling ([6fdcb04](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/6fdcb04364b92ed06c0ebc80001af412647022a0))

## [1.5.1](https://github.com/tekgnosis-net/pdf-rag-mcp-server/compare/v1.5.0...v1.5.1) (2025-11-08)


### Bug Fixes

* harden vector rebuild model loading ([652ce1c](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/652ce1ce775c853e073132e90a60f88b2d3a3709))

# [1.5.0](https://github.com/tekgnosis-net/pdf-rag-mcp-server/compare/v1.4.0...v1.5.0) (2025-11-08)


### Features

* enhance semantic search responses and mcp docs ([0065130](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/0065130bb9dff724d987573f729edb069474f6f8))

# [1.4.0](https://github.com/tekgnosis-net/pdf-rag-mcp-server/compare/v1.3.0...v1.4.0) (2025-11-08)


### Features

* add lance vector backend with async rebuild ([f2352cc](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/f2352ccfe9039ec24498e8f034ff9b5bdebdd24d))

# [1.3.0](https://github.com/tekgnosis-net/pdf-rag-mcp-server/compare/v1.2.1...v1.3.0) (2025-11-08)


### Features

* **vector-store:** rebuild embeddings from markdown on reset ([490838d](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/490838d5ac9bde9b8272258ddc218c8fdd54e249))

## [1.2.1](https://github.com/tekgnosis-net/pdf-rag-mcp-server/compare/v1.2.0...v1.2.1) (2025-11-08)


### Bug Fixes

* **vector-store:** recover from corrupted chroma state ([caa1600](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/caa1600ca94383bf6970fac6805123a2e9bec7ad))

# [1.2.0](https://github.com/tekgnosis-net/pdf-rag-mcp-server/compare/v1.1.0...v1.2.0) (2025-11-08)


### Features

* **search:** add paginated search ui and api ([ad49ab0](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/ad49ab04b548f3c063caf85caeb4f9582178afd9))

# [1.1.0](https://github.com/tekgnosis-net/pdf-rag-mcp-server/compare/v1.0.0...v1.1.0) (2025-11-08)


### Features

* **settings:** add blacklist management UI ([8aa1216](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/8aa1216a747c062eb8e9a0955f542b249f5bd2d9))

# 1.0.0 (2025-11-08)


### Bug Fixes

* align websocket port with current host ([74eb8be](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/74eb8becd1f79b158dc2ba4009a4b9a480a076d8))
* ensure uv available and allow local docker builds ([74255a7](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/74255a7dc3d1345ce8ad49080bc0f88c55df7be8))
* persist sqlite db across restarts ([783054f](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/783054fdcba1197f778542a9fb95f24af4d8ab79))
* point entrypoint to /app ([7e3c5f4](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/7e3c5f42b02277fea3397d4928c99067e1eb46ef))
* prepare sqlite volume at startup ([e8488a1](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/e8488a19cd63361d4d95cc3fbc13e814420d4c8d))
* run docker publish on master ([9136dc5](https://github.com/tekgnosis-net/pdf-rag-mcp-server/commit/9136dc5fdc540a2f5a68adbd677f76dd61fe9e3b))

# Changelog

All notable changes to this project will be documented in this file by [semantic-release](https://github.com/semantic-release/semantic-release).
