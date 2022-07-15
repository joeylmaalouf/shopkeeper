#!/usr/bin/python

# imported modules
from PIL import Image, ImageDraw, ImageFont, ImageOps
import json
import re
import requests
import sys

# configuration constants
BUILD_IMAGE_DIMENSIONS = (1920, 1080)
BACKGROUND_ALPHA = 55
DRAW_COLOR = (50, 50, 50)
BACK_COLOR = (0, 0, 0)
TEXT_COLOR = (100, 100, 100)
TRANSPARENCY_THRESHOLD = 64
LETTER_OPTIONS = ('Q', 'W', 'E', 'R')
ABILITY_IMAGE_CHARACTER = '@' # a character that wouldn't normally show up in the ability order
FONT_SIZES = {
	'H1': 48,
	'H2': 40,
	'H3': 32,
	'H4': 24
}
FONT_HEIGHT_BONUS = 2 # the font is usually drawn a few pixels short of its supposed height
FONT_FILEPATH = '../shared/CarroisGothicSC-Regular.ttf'
WIKI_BASE_URL = 'https://leagueoflegends.fandom.com/wiki'
WIKI_IMAGE_URL_PATTERN = r'https://static\.wikia\.nocookie\.net/leagueoflegends/images/.+?\.(?:jpg|png)'
ENCHANTABLE_ITEMS = ['Stalker\'s Blade', 'Skirmisher\'s Sabre', 'Pridestalker\'s Blade', 'Tracker\'s Knife',  'Ranger\'s Trailblazer',  'Poacher\'s Knife']


# main: loads the given data from sys_argv and runs each draw function in succession to get the final image
def main(sys_argv):
	if len(sys_argv) < 2:
		print('Error: no input file given.')
		sys.exit(1)
	elif not sys_argv[1].endswith('.json'):
		print('Error: argument must be a .json file.')
		sys.exit(1)

	# we're gonna put the output image in the same location as the input json, just with a different extension
	input_filepath = sys_argv[1]
	output_filepath = re.sub(r'\.json$', '.png', input_filepath)

	with open(input_filepath) as input_filehandle:
		build_data = json.load(input_filehandle)

	# the base image is pure black, then we draw each layer on top of it
	build_image = Image.new('RGB', BUILD_IMAGE_DIMENSIONS, (0, 0, 0))
	for draw_function in (draw_background, draw_metadata, draw_summoner_spells, draw_runes, draw_abilities, draw_items):
		build_image = draw_function(build_image, build_data)
		print("Finished step: " + draw_function.__name__)

	if build_image:
		build_image.save(output_filepath)
		print('Success: created "%s" from "%s".' % (output_filepath, input_filepath))
		sys.exit(0)
	else:
		print('Error: something went wrong while creating the build image. Perhaps malformed data?')
		sys.exit(1)


# draw_background: gets the skin image for the loaded build_data and draws it on build_image as the background
def draw_background(build_image, build_data):
	skin_images = get_images(
		'/'.join((WIKI_BASE_URL, build_data.get('Champion'), 'Skins')),
		re.compile(r'data-skin="(.*?)"><a href="(%s)' % WIKI_IMAGE_URL_PATTERN)
	)
	skin_image = skin_images.get(build_data.get('Skin').replace('\'', '&#39;'))

	if skin_image:
		# scale the skin image to fit the width of the build image
		image_width, image_height = skin_image.size
		scale_ratio = float(BUILD_IMAGE_DIMENSIONS[0]) / image_width
		skin_image = skin_image.resize((int(image_width * scale_ratio), int(image_height * scale_ratio)))

		# then center and crop the skin image to fit the height of the build image
		image_width, image_height = skin_image.size
		height_difference = image_height - BUILD_IMAGE_DIMENSIONS[1]
		top_cut = height_difference / 2
		bottom_cut = height_difference - top_cut
		skin_image = skin_image.crop((0, top_cut, BUILD_IMAGE_DIMENSIONS[0], image_height - bottom_cut))

		# make it mostly transparent so it's not a distracting background
		skin_image.putalpha(BACKGROUND_ALPHA)
		build_image.paste(skin_image, (0, 0), skin_image)
	return build_image


# draw_metadata: loads the metadata text from build_data and draws them on build_image in the corners
def draw_metadata(build_image, build_data):
	# load our font in all of the sizes we need for the metadata
	scaled_fonts = {}
	for header_level, font_size in FONT_SIZES.items():
		scaled_fonts[header_level] = ImageFont.truetype(FONT_FILEPATH, font_size)
	metadata_drawer = ImageDraw.Draw(build_image)

	# draw each of the pieces offset from the specified corner
	for text_anchor, text_offset, metadata_type, header_level in [
		(('left' , 'top'   ), (32, 32), 'Champion', 'H1'),
		(('left' , 'top'   ), (32, 88), 'Role'    , 'H2'),
		(('right', 'bottom'), (32, 32), 'Skin'    , 'H2'),
		(('right', 'bottom'), (32, 80), 'Chroma'  , 'H3'),
		(('left' , 'bottom'), (32, 32), 'Creator' , 'H4'),
		(('right', 'top'   ), (32, 32), 'Patch'   , 'H4'),
	]:
		metadata_text = build_data.get(metadata_type)
		if not metadata_text:
			continue
		scaled_font = scaled_fonts[header_level]
		text_width, text_height = metadata_drawer.textsize(metadata_text, scaled_font)
		text_position = (
			0 + text_offset[0] if text_anchor[0] == 'left' else BUILD_IMAGE_DIMENSIONS[0] - (text_offset[0] + text_width ),
			0 + text_offset[1] if text_anchor[1] == 'top'  else BUILD_IMAGE_DIMENSIONS[1] - (text_offset[1] + text_height)
		)
		metadata_drawer.text(text_position, metadata_text, TEXT_COLOR, scaled_font)
	return build_image


# draw_summoner_spells: gets the summoner spell images for the loaded build_data and draws them on build_image side by side
def draw_summoner_spells(build_image, build_data):
	spell_images = get_images(
		'/'.join((WIKI_BASE_URL, 'Summoner_spell')),
		re.compile(r'<div class="grid-image label-after spell-icon" data-param="(\w+).*?data-src="(%s)' % WIKI_IMAGE_URL_PATTERN, re.DOTALL)
	)

	x_offset, y_offset = 128, 256
	for spell_name in build_data.get('Summoner Spells'):
		spell_image = spell_images.get(spell_name)
		if spell_image:
			build_image.paste(ImageOps.expand(spell_image, 1, DRAW_COLOR), (x_offset, y_offset))
			x_offset += 160
	return build_image


# draw_runes: gets the rune images for the loaded build_data and draws them on build_image in two columns, keystone/primary and secondary/shards
def draw_runes(build_image, build_data):
	path_images = get_images(
		'/'.join((WIKI_BASE_URL, 'Rune')),
		re.compile(r'<li><img alt="(\w+) icon.png".*?data-src="(%s)' % WIKI_IMAGE_URL_PATTERN),
		False
	)
	keystone_images = get_images(
		'/'.join((WIKI_BASE_URL, 'Rune')),
		re.compile(r'title="([\w :;&#]+)".*?data-src="(%s/revision/latest/scale-to-width-down/52)' % WIKI_IMAGE_URL_PATTERN),
		False,
		{ '52': '112' } # the image is 52px on this page, but we want it at 112px; we can't just use the base link because it's 256px there
	)
	rune_images = get_images(
		'/'.join((WIKI_BASE_URL, 'Rune')),
		re.compile(r'title="([\w :;&#]+)".*?data-src="(%s/revision/latest/scale-to-width-down/52)' % WIKI_IMAGE_URL_PATTERN),
		False,
		{ '52': '64' } # the image is 52px on this page, but we want it at 64px; we can't just use the base link because it's 108px there
	)
	shard_images = get_images(
		'/'.join((WIKI_BASE_URL, 'Rune')),
		re.compile(r'data-image-name="Rune shard ([\w ]+)\.png".*?data-src="(%s/revision/latest/scale-to-width-down/30)' % WIKI_IMAGE_URL_PATTERN),
		False,
		{ '30': '32' } # the image is 30px on this page, but we want it at 32px; we can't just use the base link because it's 35px there
	)

	# path images
	rune_data = build_data.get('Runes')
	x_center_line = 128 + 1 + int(64 / 2)
	x_offset, y_offset = x_center_line - int(85 / 2), 448
	for path_name in rune_data.get('Paths'):
		path_image = path_images.get(path_name.replace('\'', '&#39;'))
		if path_image:
			# remove the half-transparent backgrounds of these images
			pixel_array = path_image.load()
			for i in range(path_image.size[0]):
				for j in range(path_image.size[1]):
					if pixel_array[i, j][3] < TRANSPARENCY_THRESHOLD:
						pixel_array[i, j] = (0, 0, 0, 0)
			build_image.paste(path_image, (x_offset, y_offset), path_image)
			x_offset += 160

	# keystone image
	x_offset = x_center_line - int(112 / 2)
	y_offset += 85 + 32
	keystone_name = rune_data.get('Primary')[0] # just get the keystone, we'll do the others below
	keystone_image = keystone_images.get(keystone_name.replace('\'', '&#39;'))
	if keystone_image:
		build_image.paste(keystone_image, (x_offset, y_offset), keystone_image)

	# primary images
	x_offset = x_center_line - int(64 / 2)
	y_offset += 112 + int(32 / 2)
	for rune_name in rune_data.get('Primary')[1:]: # skip the keystone, we did that above
		rune_image = rune_images.get(rune_name.replace('\'', '&#39;'))
		if rune_image:
			build_image.paste(rune_image, (x_offset, y_offset), rune_image)
			y_offset += 64 + 32

	# secondary images
	x_offset = x_center_line - int(64 / 2) + 160
	y_offset = 448 + 85 + 32 + 112 - 64 - 32
	for rune_name in rune_data.get('Secondary'):
		rune_image = rune_images.get(rune_name.replace('\'', '&#39;'))
		if rune_image:
			build_image.paste(rune_image, (x_offset, y_offset), rune_image)
			y_offset += 64 + 32

	# shard images
	x_offset = x_center_line - int(32 / 2) + 160
	y_offset += 16
	for shard_name in rune_data.get('Shards'):
		shard_image = shard_images.get(shard_name.replace('\'', '&#39;'))
		if shard_image:
			build_image.paste(shard_image, (x_offset, y_offset), shard_image)
			y_offset += 32 + 32

	return build_image


# draw_abilities: gets the ability images for the loaded build_data and draws them on build_image
# with level numbers and ability letters for each ability listed in the build data's ability order
def draw_abilities(build_image, build_data):
	ability_images = get_images(
		'/'.join((WIKI_BASE_URL, build_data.get('Champion'), 'LoL')),
		re.compile(r'<div class="skill skill_(\w)".*?data-source="primary_icon">\s*?<a href="(%s)' % WIKI_IMAGE_URL_PATTERN, re.DOTALL)
	)
	ability_drawer = ImageDraw.Draw(build_image)

	x_offset, y_offset = BUILD_IMAGE_DIMENSIONS[0] - 96, 96
	ability_order = build_data.get('Abilities')
	ability_level = len(ability_order)

	for ability_letter in reversed(ABILITY_IMAGE_CHARACTER + ability_order):
		if ability_letter != ABILITY_IMAGE_CHARACTER:
			outline_rectangle = ((x_offset - 65, y_offset), (x_offset, y_offset + 33))
			ability_drawer.rectangle(outline_rectangle, None, DRAW_COLOR)
			build_image = center_text(build_image, outline_rectangle, str(ability_level), 20)
		y_offset += 33

		for letter_option in LETTER_OPTIONS:
			outline_rectangle = ((x_offset - 65, y_offset), (x_offset, y_offset + 65))
			ability_drawer.rectangle(outline_rectangle, None, DRAW_COLOR)
			if ability_letter == ABILITY_IMAGE_CHARACTER:
				build_image.paste(ability_images.get(letter_option.lower()), (x_offset - 65 + 1, y_offset + 1))
			elif ability_letter.upper() == letter_option:
				build_image = center_text(build_image, outline_rectangle, letter_option, 20)
			y_offset += 65

		ability_level -= 1
		x_offset -= 65
		y_offset = 96
	return build_image


# draw_items: gets the item images for the loaded build_data and draws them on build_image split out by section
def draw_items(build_image, build_data):
	item_images = get_images(
		'/'.join((WIKI_BASE_URL, 'Item')),
		re.compile(r'<div class="item-icon".*?data-item="(.*?)".*?src="(%s)' % WIKI_IMAGE_URL_PATTERN, re.DOTALL)
	)
	item_drawer = ImageDraw.Draw(build_image)

	ability_section_end = 97 + 33 + 65 * len(LETTER_OPTIONS) # calculate the bottom of the ability section and go from there
	x_offset, y_offset = BUILD_IMAGE_DIMENSIONS[0] - 96, ability_section_end + 128
	for item_section in reversed(build_data.get('Items')):
		item_options = item_section.get('Options')

		# create sublists so no column is too long
		sublist_limit = 4
		sublist_count = (len(item_options) + sublist_limit - 1) // sublist_limit
		option_lists = [item_options[i * sublist_limit:(i + 1) * sublist_limit] for i in range(sublist_count)]

		# draw each item section label centered below the item images
		block_width = ((sublist_count * 2 - 1) * 65)
		block_height = (4 * 65 + 3 * 33)
		outline_rectangle = ((x_offset - block_width, y_offset + block_height + 33), (x_offset, y_offset + block_height + 49))
		build_image = center_text(build_image, outline_rectangle, item_section.get('Label'), 24)

		for option_list in reversed(option_lists):
			# we want to vertically center any column that doesn't have the full number of items
			y_offset += 49 * (sublist_limit - len(option_list))

			for item_name in option_list:
				outline_rectangle = ((x_offset - 65, y_offset), (x_offset, y_offset + 65))
				item_drawer.rectangle(outline_rectangle, BACK_COLOR, DRAW_COLOR)

				# we have special logic for getting enchantable item images, if they have a valid enchantment specified in parentheses
				item_image = None
				for enchantable_item in ENCHANTABLE_ITEMS:
					if re.search(r'^%s \(.*?\)$' % enchantable_item, item_name):
						enchantment_images = get_images(
							'/'.join((WIKI_BASE_URL, enchantable_item)),
							re.compile(r'<img (?:style="" )?src="(%s).*?".*?alt="(?:[^"]*?\()?(.+?)(?:\)[^"]*?)?"' % WIKI_IMAGE_URL_PATTERN),
							True
						)
						for enchantment_name in enchantment_images.keys():
							if item_name == '%s (%s)' % (enchantable_item, enchantment_name):
								item_image = enchantment_images.get(enchantment_name)
								break
						else:
							# fall back on using the base image if the given enchantment doesn't match any of the ones found
							item_image = item_images.get(enchantable_item.replace('\'', '&#39;'))
						break
				# use the base image if there's no enchantment specified
				# which is the most likely option, since only the old jungle items have enchantments
				else:
					item_image = item_images.get(item_name.replace('\'', '&#39;'))

				if item_image:
					item_mask = item_image if 'A' in item_image.mode else None
					build_image.paste(item_image, (x_offset - 65 + 1, y_offset + 1), item_mask)
				y_offset += 33 + 65

			x_offset -= 65 + 65
			y_offset = ability_section_end + 128
		x_offset -= 65
	return build_image


# get_images: parses the source of wiki_page for every match to image_regex, creating a mapping of the text in the first
# capture group to the downloaded image located at the url in the second capture group; switches the key and value if
# reverse_order is given, and applies any link_modifiers find:replace pairs to the url before downloading the image
def get_images(wiki_page, image_regex, reverse_order = False, link_modifiers = None):
	page_source = requests.get(wiki_page).text
	image_links = image_regex.findall(page_source) # the regex should parse the page for paired groups in each match
	image_map = {}
	for image_key, image_link in image_links: # each of the pairs should be a link to an image and a way to refer to it (potentially reversed)
		if image_key in image_map:
			continue
		if reverse_order:
			image_key, image_link = image_link, image_key
		if link_modifiers:
			for old_regex, new_string in link_modifiers.items():
				image_link = re.sub(old_regex, new_string, image_link)
		image_map[image_key] = Image.open(requests.get(image_link, stream = True).raw) # we create a mapping of each key to its downloaded image
	return image_map


# center_text: centers draw_text in the outline_rectangle bounding box, drawing it on build_image in size font_size text
def center_text(build_image, outline_rectangle, draw_text, font_size):
	outline_width = outline_rectangle[1][0] - outline_rectangle[0][0]
	outline_height = outline_rectangle[1][1] - outline_rectangle[0][1]
	text_drawer = ImageDraw.Draw(build_image)
	scaled_font = ImageFont.truetype(FONT_FILEPATH, font_size)
	text_width, text_height = text_drawer.textsize(draw_text, scaled_font)
	text_position = (
		outline_rectangle[0][0] + int((outline_width - text_width) / 2),
		outline_rectangle[0][1] + int((outline_height - text_height) / 2) - FONT_HEIGHT_BONUS
	)
	text_drawer.text(text_position, draw_text, TEXT_COLOR, scaled_font)
	return build_image


# standard ifmain with args
if __name__ == '__main__':
	main(sys.argv)
