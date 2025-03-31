
def split_into_blocks(items, size):
    """Splits a list into blocks that contain at most 'size' items.
    """
    blocks = []
    while items:
        blocks.append(items[:size])
        items = items[size:]

    return blocks
