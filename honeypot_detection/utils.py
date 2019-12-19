def address_list_from_file(address_list_file):
    return [line.strip().lower() for line in address_list_file.readlines()]
