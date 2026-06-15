
# Adding new translated texts to the Tellae plugin

This plugin uses **QTranslator** for the application translation and **QtLinguist**
the creation of new translations, stored in .ts and .qm files.

The original texts (used as keys) are in french.

For now, only an english translation file is available.

## Update the plugin part needing translation

### User interface files (.ui)

Create or edit a widget. Write the original french text in the relevant properties.
For instance, a `QLabel` widget has a `text` property.
Keep the _translatable_ checkbox ticked (default).

### Python files (.py)

Import the `tr` function (from tellae.utils) and call it on the original french text.

Use brackets `{}` as placeholders 

```python
from tellae.utils import tr

print(
    tr("La couche '{}' a été ajoutée avec succès").format('Nom de la couche')
)
```

## Update the translation file with new source texts

The `pylupdate5` command (provided with **QtLinguist**) looks for the translatable strings
in user interface files and the calls to `tr` in Python files.
Then it adds new untranslated entries to the given .ts file.

Note that the .ts files should be named 'tellae_{locale}.ts' with {locale}
being the first two letters of the Qgis locale value.

```bash
# include subfolders
shopt -s globstar

# update translations from all .py files and all .ui files in dialogs/
# add the newly found source texts in the tellae_en.ts translation file
pylupdate5 **/*.py dialogs/*.ui -ts i18n/tellae_en.ts -verbose

# -noobsolete to drop obsolete entries
```

## Translate the new source texts

Open the translation file (.ts) in **QtLinguist**.

Look for an untranslated string (shortcut: Ctrl + J), translate it in the target language, and validate the translation (shortcut: Ctrl + Enter).

See the [QtLinguist manual](https://qthub.com/static/doc/qt5/qtlinguist/linguist-translators.html) for more info.

When you are done, save the file and close **QtLinguist**.

## Compile the translation file

Finally, generate a compiled translation file (.qm).

```bash
# this will create a tellae_en.qm file
lrelease i18n/tellae_en.ts
```