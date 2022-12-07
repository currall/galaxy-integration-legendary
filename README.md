# Legendary Integration for GOG Galaxy

Allows you to install, launch and uninstall your Epic Games library through the open-source alternative to the Epic Games Launcher - Legendary launcher (https://github.com/derrod/legendary)

This integration is only tested on Windows. It may work on other platforms, but I doubt it.

### Automatic

1. Download source code
2. Run "install_plugin.bat"

### Manual

1. Copy the plugin to %localappdata%\GOG.com\Galaxy\plugins\installed\GalaxyPluginEpic.
2. Set the location of your prefered "legendary.exe" in config.txt. If left blank will just use included version.

### Scoop

```
scoop bucket add dank-scoop https://github.com/brian6932/dank-scoop/
```
```
scoop install galaxy-integration-legendary
```

Credit to Countryen for the GOG generic integration, I used parts of their integration to make this.

https://github.com/Countryen/gog-generic-integration

Credit to Epic Games for the default Epic Games integration