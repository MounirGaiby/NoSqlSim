{
  description = "NoSqlSim - MongoDB Replication & Consistency Simulator";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        
        pythonEnv = pkgs.python312.withPackages (ps: with ps; [
          fastapi
          uvicorn
          pymongo
          docker
          requests
          pydantic
          pydantic-settings
          websockets
          python-dotenv
          pytest
          pytest-asyncio
          httpx
          python-multipart
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            pythonEnv
            nodejs_20
            pnpm
            just
            docker
            docker-compose
            curl
            jq
          ];

          shellHook = ''
            echo ""
            echo "=========================================="
            echo "  NoSqlSim Development Environment"
            echo "=========================================="
            echo ""
            echo "Available commands (via just):"
            echo "  just setup    - Install all dependencies"
            echo "  just start    - Start backend and frontend"
            echo "  just stop     - Stop all services"
            echo "  just logs     - View backend logs"
            echo "  just test     - Run integration tests"
            echo "  just clean    - Remove all containers and data"
            echo ""
            echo "Manual commands:"
            echo "  just backend  - Start backend only"
            echo "  just frontend - Start frontend only"
            echo ""
            
            export PYTHONPATH="$PWD/backend:$PYTHONPATH"
            export PATH="$PWD/node_modules/.bin:$PATH"
          '';
        };

        packages.default = pkgs.writeShellScriptBin "nosqlsim" ''
          cd ${self}
          ${pkgs.just}/bin/just "$@"
        '';
      }
    );
}
