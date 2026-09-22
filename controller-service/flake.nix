{
  description = "Nix flake for controller-service (Controls team).";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/25.11";
  };
  outputs =
    { self, nixpkgs, ... }:
    let
      eachSystem = nixpkgs.lib.genAttrs [ "x86_64-linux" "aarch64-darwin" "aarch64-linux" ];
    in
    {
      packages = eachSystem (system:
        let
          pkgs = import nixpkgs { inherit system; };
          controllerService = pkgs.writers.writePython3Bin "controller-service" {
            flakeIgnore = [ "E265" "E501" ];
          } (builtins.readFile ./main.py);
        in
        {
          default = controllerService;
          docker = pkgs.dockerTools.buildLayeredImage {
            name = "controller-service";
            tag = "latest";
            config.Cmd = [ "${controllerService}/bin/controller-service" ];
          };
        }
      );

      devShells = eachSystem (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.mkShell {
            name = "controller-service-dev";
            packages = [
              pkgs.python311
              self.packages.${system}.default
            ];
          };
        }
      );
    };
}
