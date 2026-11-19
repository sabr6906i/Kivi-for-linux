#!/usr/bin/env bash
# CI-only reliability settings; never change a developer's host repositories.
set -euo pipefail
if [[ ${GITHUB_ACTIONS:-} != true ]]; then
    echo 'This helper is restricted to disposable GitHub Actions Ubuntu runners.' >&2
    exit 2
fi
sudo python3 - <<'PY'
from pathlib import Path
# Keep Ubuntu's configured signing keys/suites intact; only normalize mirrors.
for name,url in [('apt-mirrors.txt','https://archive.ubuntu.com/ubuntu/'),
                 ('apt-mirrors-security.txt','https://security.ubuntu.com/ubuntu/')]:
    path=Path('/etc/apt')/name
    if path.exists():path.write_text(url+'\n')
Path('/etc/apt/apt.conf.d/99bol-ci-network').write_text('Acquire::Retries "2";\nAcquire::http::Timeout "20";\nAcquire::https::Timeout "20";\n')
PY
