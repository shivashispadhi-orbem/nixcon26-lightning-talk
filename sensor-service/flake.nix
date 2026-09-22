{
  description = "Nix flake for sensor-service (Sensing team).";
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
          sensorService = pkgs.writers.writePython3Bin "sensor-service" {
            flakeIgnore = [ "E265" "E501" ];
          } (builtins.readFile ./main.py);
        in
        {
          default = sensorService;
          docker = pkgs.dockerTools.buildLayeredImage {
            name = "sensor-service";
            tag = "latest";
            config.Cmd = [ "${sensorService}/bin/sensor-service" ];
          };
        }
      );

      devShells = eachSystem (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.mkShell {
            name = "sensor-service-dev";
            packages = [
              pkgs.python311
              self.packages.${system}.default
            ];
          };
        }
      );
    };
}
