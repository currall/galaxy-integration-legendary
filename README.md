# Legendary Integration for GOG Galaxy

Allows you to install, launch and uninstall your Epic Games library through the open-source alternative to the Epic Games Launcher - Legendary launcher (https://github.com/derrod/legendary)

### Manual

1. Install the plugin to %localappdata%\GOG.com\Galaxy\plugins\installed\GalaxyPluginEpic.
2. Legendary must already be present on the user's computer. Specify the legendary location in config.txt.
3. This integration is only tested on Windows. It may work on other platforms, but I doubt it.

### Scoop

```
scoop bucket add dank-scoop https://github.com/brian6932/dank-scoop/
```
```
scoop install galaxy-integration-legendary
```

Credit to Countryen for the GOG generic integration, I used parts of their integration to make this.

https://github.com/Countryen/gog-generic-integration

Also credit to GOG for the official Epic integration, I used their authentication code.
