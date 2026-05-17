# Copyright 2026 AshGrey <ashgrey.huaier@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in the
# Software without restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the
# following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

{
  description = "The project repo of THUAI-9 Skies of Tactics competition";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      allSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs allSystems (system: f {
        pkgs = import nixpkgs { inherit system; };
      });
    in
    {
      packages = forAllSystems ({ pkgs }: {
        build = pkgs.writeShellApplication {
          name = "build";
          runtimeInputs = [ pkgs.zip ];
          text = ''
            # Capture the project root path cleanly before jumping directories
            PROJECT_ROOT="''$(pwd)"
            OUT_DIR="''${PROJECT_ROOT}/build"

            echo "→ output directory is ''${OUT_DIR}"

            exclude=(
              "__pycache__/*"
              ".mypy_cache/*"
              ".ruff_cache/*"
              ".venv/*"
              "*/__pycache__/*"
              "*/.mypy_cache/*"
              "*/.ruff_cache/*"
              "*/.venv/*"
            )
            set -eu
            timestamp=''$(date +%Y%m%d-%H%M%S)
            mkdir -p "''${OUT_DIR}"

            pushd "''${PROJECT_ROOT}/src" > /dev/null
            # Expand the array correctly using "''${exclude[@]}"
            zip -r "''${OUT_DIR}/nightly-''${timestamp}.zip" . -x "''${exclude[@]}"
            echo "→ Built ''${OUT_DIR}/nightly-''${timestamp}.zip"
            popd > /dev/null
          '';
        };
      });
      devShells = forAllSystems ({ pkgs }: {
        default = pkgs.mkShell {
          packages = with pkgs; [
            uv
            fish
          ];

          shellHook = ''
            echo "→ Environment has been set up"
            pushd ./src
            uv venv
            source .venv/bin/activate.fish
            uv pip install -r requirements.txt
            popd
          '';
        };
      });
    };
}
