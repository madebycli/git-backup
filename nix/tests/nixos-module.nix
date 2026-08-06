{
  pkgs,
  module,
  package,
}:
pkgs.testers.nixosTest {
  name = "github-backup-deck-module";
  nodes.machine = {
    imports = [ module ];
    programs.github-backup-deck = {
      enable = true;
      inherit package;
    };
  };
  testScript = ''
    machine.start()
    machine.wait_for_unit("multi-user.target")
    machine.succeed("command -v github-backup-deck")
    machine.succeed("github-backup-deck --help >/dev/null")
    machine.succeed("github-backup-deck doctor >/tmp/doctor.json")
    machine.succeed("grep -q '\"ok\": true' /tmp/doctor.json")
    machine.succeed("test -f /run/current-system/sw/share/applications/github-backup-deck.desktop")
    machine.succeed("test -f /run/current-system/sw/share/applications/github-backup-deck-overview.desktop")
    machine.succeed("test ! -e /etc/github-backup-deck/token")
    machine.fail("systemctl list-unit-files | grep -q github-backup-deck.service")
  '';
}
