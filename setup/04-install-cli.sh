#!/usr/bin/env bash
# Setup step 4 - install the `vibe` platform CLI on this laptop.
# Creates a symlink ~/.local/bin/vibe -> scripts/vibe (re-run is harmless).
set -euo pipefail
. "$(dirname "$0")/../scripts/_common.sh"

BIN_DIR="${VIBE_BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$BIN_DIR"
chmod +x "$ROOT/scripts/vibe" "$ROOT"/scripts/*.sh
ln -sf "$ROOT/scripts/vibe" "$BIN_DIR/vibe"
ok "vibe -> $ROOT/scripts/vibe (link in $BIN_DIR)"

case ":$PATH:" in
  *":$BIN_DIR:"*) ok "$BIN_DIR is in your PATH" ;;
  *)
    warn "$BIN_DIR is not in your PATH. Add it (zsh):"
    echo "    echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> ~/.zshrc && source ~/.zshrc"
    ;;
esac

if command -v vibe >/dev/null 2>&1; then
  echo
  vibe help
fi
