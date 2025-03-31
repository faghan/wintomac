import tarfile
import os

def untar_file(file_path, extract_path='.'):
    """
    Extracts a .tar file to a specified directory.

    Parameters:
    file_path (str): The path to the .tar file.
    extract_path (str): The directory to extract the contents to. Defaults to the current directory.
    """
    if not os.path.isfile(file_path):
        print(f"File {file_path} does not exist.")
        return

    if not tarfile.is_tarfile(file_path):
        print(f"File {file_path} is not a valid .tar file.")
        return

    try:
        with tarfile.open(file_path, 'r') as tar:
            tar.extractall(path=extract_path)
            print(f"Extracted {file_path} to {extract_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
file_path = r"/home/faghan/repos/tar-test/test.tar"  # Replace with your .tar file path
extract_path = r"/home/faghan/repos/tar-test"  # Replace with your desired extract directory or use '.' for current directory

untar_file(file_path, extract_path)
