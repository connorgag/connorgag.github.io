Command for Conversion and Cleanup:

# 1. Convert and resize images
magick mogrify -resize "1600x1600>" -format webp -quality 80 *.jpg *.jpeg

# 2. Delete the original files
rm *.jpg *.jpeg