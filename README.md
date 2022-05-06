# Legendary Integration for GOG Galaxy

Allows you to install, launch and uninstall your Epic Games library through the open-source alternative to the Epic Games Launcher - Legendary launcher (https://github.com/derrod/legendary)

1. Install the plugin to %localappdata%\GOG.com\Galaxy\plugins\installed\galaxy-integration-legendary.
2. Legendary must already be present on the user's computer. Specify the legendary location in config.txt.
3. This plugin uses the Humble Bundle platform. If you have Humble games in GOG already replace the "humble" in manifest.json to another platform. Use platforms.txt to view a list of available platforms. The "epic" platform will not work as the official integration will override it. Game compatability is dependent on the platform.
4. Some games do not work. They will be missing titles and box art, and will not let you install them. You can launch them if already installed in legendary.
5. This integration is only tested on Windows. It may work on other platforms, but I doubt it.

Credit to Countryen for the GOG generic integration, I used parts of their integration to make this.

https://github.com/Countryen/gog-generic-integration
