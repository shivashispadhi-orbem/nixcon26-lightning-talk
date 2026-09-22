{
  pkgs,
  sensor-service-pkg,
  actuator-service-pkg,
  controller-service-pkg,
  telemetry-service-pkg,
}:
let
  busUrl = "http://localhost:9000";
  sensorUrl = "http://localhost:8001";
  actuatorUrl = "http://localhost:8002";
  controllerUrl = "http://localhost:8003";

  ready = port: path: {
    http_get = {
      host = "127.0.0.1";
      inherit port path;
    };
    initial_delay_seconds = 1;
    period_seconds = 1;
    failure_threshold = 30;
  };

  healthy = names: pkgs.lib.genAttrs names (_: { condition = "process_healthy"; });

  service = port: attrs: attrs // {
    readiness_probe = ready port "/healthz";
    availability.restart = "on_failure";
  };

  services = [ "sensor-service" "actuator-service" "controller-service" "telemetry-service" ];
in
{
  cli.environment.PC_DISABLE_TUI = true;
  cli.preHook = "rm -rf .data && mkdir -p .data";

  settings.processes = {
    hardware-bus-mock = service 9000 {
      command = "${pkgs.python311}/bin/python3 ${./hardware_bus_mock.py}";
      environment.BUS_PORT = "9000";
    };

    sensor-service = service 8001 {
      command = "${sensor-service-pkg}/bin/sensor-service";
      environment = {
        SENSOR_PORT = "8001";
        HARDWARE_BUS_URL = busUrl;
      };
      depends_on = healthy [ "hardware-bus-mock" ];
    };

    actuator-service = service 8002 {
      command = "${actuator-service-pkg}/bin/actuator-service";
      environment = {
        ACTUATOR_PORT = "8002";
        HARDWARE_BUS_URL = busUrl;
      };
      depends_on = healthy [ "hardware-bus-mock" ];
    };

    controller-service = service 8003 {
      command = "${controller-service-pkg}/bin/controller-service";
      environment = {
        CONTROLLER_PORT = "8003";
        SENSOR_SERVICE_URL = sensorUrl;
        ACTUATOR_SERVICE_URL = actuatorUrl;
        CONTROLLER_POLL_INTERVAL_SECONDS = "0.5";
      };
      depends_on = healthy [ "sensor-service" "actuator-service" ];
    };

    telemetry-service = service 8004 {
      command = "${telemetry-service-pkg}/bin/telemetry-service";
      environment = {
        TELEMETRY_PORT = "8004";
        SENSOR_SERVICE_URL = sensorUrl;
        ACTUATOR_SERVICE_URL = actuatorUrl;
        CONTROLLER_SERVICE_URL = controllerUrl;
        TELEMETRY_POLL_INTERVAL_SECONDS = "0.5";
      };
      depends_on = healthy [ "sensor-service" "actuator-service" "controller-service" ];
    };

    prometheus = {
      command =
        "${pkgs.prometheus}/bin/prometheus --config.file=${./provisioning/prometheus.yml} "
        + "--storage.tsdb.path=.data/prometheus";
      depends_on = healthy services;
      readiness_probe = ready 9090 "/-/ready";
      availability.restart = "on_failure";
    };

    # Named `test` so process-compose-flake exposes it as outputs.testPackage.
    test = {
      command = "${pkgs.python311}/bin/python3 -u ${./tests/test_control_loop.py}";
      depends_on = healthy services;
      disabled = true;
    };
  };
}
