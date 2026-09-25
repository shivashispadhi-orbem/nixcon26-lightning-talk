{
  description = "Nix flake for actuator-service.";
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
          actuatorService = pkgs.writers.writePython3Bin "actuator-service" {
            flakeIgnore = [ "E265" "E501" ];
          } (builtins.readFile ./main.py);
        in
        {
          default = actuatorService;
          docker = pkgs.dockerTools.buildLayeredImage {
            name = "actuator-service";
            tag = "latest";
            config.Cmd = [ "${actuatorService}/bin/actuator-service" ];
          };
        }
      );

      devShells = eachSystem (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.mkShell {
            name = "actuator-service-dev";
            packages = [
              pkgs.python311
              self.packages.${system}.default
            ];
          };
        }
      );
    };
}
