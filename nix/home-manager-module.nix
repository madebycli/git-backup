{ self }:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.programs.github-backup-deck;
  settingsFormat = pkgs.formats.json { };
in
{
  options.programs.github-backup-deck = {
    enable = lib.mkEnableOption "GitHub Backup Deck";
    package = lib.mkOption {
      type = lib.types.package;
      default = self.packages.${pkgs.system}.github-backup-deck;
      defaultText = lib.literalExpression "self.packages.${pkgs.system}.github-backup-deck";
      description = "GitHub Backup Deck package to install.";
    };
    settings = lib.mkOption {
      inherit (settingsFormat) type;
      default = { };
      example = {
        default_backup_directory = "~/GitHub Backup";
        include_issues = true;
        include_pull_requests = true;
        include_releases = true;
        include_action_artifacts = false;
      };
      description = "Non-secret application preferences. Never place tokens here.";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = !(cfg.settings ? token) && !(cfg.settings ? github_token);
        message = "GitHub credentials must not be stored in Home Manager settings.";
      }
    ];
    home.packages = [ cfg.package ];
    xdg.configFile."github-backup-deck/config.json" = lib.mkIf (cfg.settings != { }) {
      source = settingsFormat.generate "github-backup-deck-config.json" cfg.settings;
    };
  };
}
