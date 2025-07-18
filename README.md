# Tellae QGIS plugin

This repository contains the code of the QGIS plugin **Tellae**.

This plugin allows accessing _Tellae_ services (for instance some of the tools available in [Kite](https://kite.tellae.fr/)) from QGIS.
This mainly consists in access to mobility-related data in France and processing algorithms.

You will need a _Tellae_ user account to use this plugin.

## Install

### Install from the QGIS plugin manager

The _Tellae_ plugin will soon be available in the QGIS plugin manager ! 
It will be tagged as _Experimental_, so make sure to tick the "Display experimental plugins" in your plugins manager parameters.

### Install from .zip file

First, [download the plugin ZIP](https://github.com/tellae/qgis-tellae-plugin/releases/latest/download/tellae_plugin.zip) from the latest release.

Then, open QGIS and click on the menu item <kbd>Plugins ► Manage and Install Plugins</kbd>. Go to the `Install from ZIP` tab, select the .zip file
from your file system and click the <kbd>Install plugin</kbd> button.

## Authentication

Upon your first use of the plugin, you will be presented with an authentication window.

**The identifiers expected here are NOT your _Tellae_ username and password.** Instead, you need to create an API key and its secret.

### API key creation

Open [Kite](https://kite.tellae.fr/) and click <kbd>API keys</kbd> in the top right menu.
Now click <kbd>Add a new API key</kbd>.

The secret will be automatically copied to your clipboard. Paste it in the _Secret_ field of the
authentication window.

Then, click on the underlined API key's identifier. This will copy it to your clipboard.
You can then paste it in the _Identifiant_ field of the authentication window.

Click <kbd>Ok</kbd>. If the authentication is successful, the authentication window should close and you should
see your name appear on the top right button of the main window.

### Authentication management

Upon successful authentication, your identifiers will be safely stored using QGIS'
authentication database system, where they will be protected by a master password.

You can find the identifiers used by the **Tellae** plugin in the 
<kbd>Authentication</kbd> tab of the <kbd>Preferences</kbd> menu, under the name `AWS-Tellae`.

## Contact

You can contact us at kite@tellae.fr

## License

qgis-tellae-plugin is free software; you can redistribute it and/or modify it under 
the terms of the GNU General Public License as published by the 
Free Software Foundation; version 3 of the License.