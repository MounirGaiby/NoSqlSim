{
  description = "NoSqlSim - MongoDB Replication & Consistency Simulator";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs supportedSystems (system: f {
        pkgs = nixpkgs.legacyPackages.${system};
      });
    in
    {
      devShells = forAllSystems ({ pkgs }: {
        default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python312
            nodejs_20
            pnpm
            just
          ];

          shellHook = ''
            echo ""
            echo "=========================================="
            echo "  NoSqlSim Development Environment"
            echo "=========================================="
            echo ""
            echo "Commands: just setup | start | stop | test | clean"
            echo ""
            export PYTHONPATH="$PWD/backend:$PYTHONPATH"
          '';
        };
      });
    };
}
