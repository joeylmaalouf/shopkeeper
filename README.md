# LoL Shopkeeper

Generates League of Legends build images from data files.

See the `examples` folder for examples (duh).

Each `.json` corresponds to a `.png`, so `python shopkeeper.py examples/sylas.json` will create `examples/sylas.png`.

If an expected key is missing from the input, its corresponding image section will be missing from the output.

Images are pulled from the [LoL wiki](https://leagueoflegends.fandom.com/wiki), so the key names should match the site.
