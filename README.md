# Shopkeeper

Generates build images from data files.

See the `examples` folder in a given game for examples (duh).

Each `.json` corresponds to a `.png`, so `python shopkeeper.py examples/sylas.json` will create `examples/sylas.png`.

If an expected key is missing from the input, its corresponding image section will be missing from the output.

Images are pulled from each game's wiki, so the key names should match those sites.
