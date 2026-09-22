{
  description = "Integration test: sensor + actuator + controller + telemetry, each packaged by its own flake.";
  inputs = {
    sensor-service.url = "github:shivashispadhi-orbem/nixcon26-lightning-talk?dir=sensor-service";
    actuator-service.url = "github:shivashispadhi-orbem/nixcon26-lightning-talk?dir=actuator-service";
    controller-service.url = "github:shivashispadhi-orbem/nixcon26-lightning-talk?dir=controller-service";
    telemetry-service.url = "github:shivashispadhi-orbem/nixcon26-lightning-talk?dir=telemetry-service";

    nixpkgs.url = "github:NixOS/nixpkgs/25.11";
    sensor-service.inputs.nixpkgs.follows = "nixpkgs";
    actuator-service.inputs.nixpkgs.follows = "nixpkgs";
    controller-service.inputs.nixpkgs.follows = "nixpkgs";
    telemetry-service.inputs.nixpkgs.follows = "nixpkgs";

    process-compose-flake.url = "github:Platonic-Systems/process-compose-flake";
  };
  outputs =
    {
      sensor-service,
      actuator-service,
      controller-service,
      telemetry-service,
      nixpkgs,
      process-compose-flake,
      ...
    }:
    let
      eachSystem = nixpkgs.lib.genAttrs [
        "x86_64-linux"
        "aarch64-darwin"
        "aarch64-linux"
      ];

      perSystem =
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          # evalModules rather than makeProcessCompose, so we get testPackage
          # alongside the plain runnable package.
          pcEval = (import process-compose-flake.lib { inherit pkgs; }).evalModules {
            modules = [
              (import ./process-compose.nix {
                inherit pkgs;
                sensor-service-pkg = sensor-service.packages.${system}.default;
                actuator-service-pkg = actuator-service.packages.${system}.default;
                controller-service-pkg = controller-service.packages.${system}.default;
                telemetry-service-pkg = telemetry-service.packages.${system}.default;
              })
            ];
          };
        in
        {
          inherit pkgs pcEval;
        };
    in
    {
      packages = eachSystem (
        system:
        let
          built = perSystem system;
        in
        {
          default = built.pcEval.config.outputs.package;
        }
      );

      # Entry point: brings the stack up, runs the assertions, tears it down
      # and exits with their status.
      apps = eachSystem (
        system:
        let
          built = perSystem system;
          testPackage = built.pcEval.config.outputs.testPackage;
        in
        {
          test = {
            type = "app";
            program = "${testPackage}/bin/${testPackage.meta.mainProgram or "process-compose-test"}";
          };
        }
      );

      devShells = eachSystem (
        system:
        let
          built = perSystem system;
        in
        {
          default = built.pkgs.mkShell {
            name = "integration-test";
            packages = [
              built.pkgs.curl
              built.pkgs.just
              built.pcEval.config.outputs.package
            ];
            shellHook = ''
              echo "  process-compose up      # start the stack, keep it up"
              echo "  nix run .#test          # one-shot: up, assert, down"
            '';
          };
        }
      );
    };
}
