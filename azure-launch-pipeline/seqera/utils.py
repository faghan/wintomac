import re


def clean_csv(csv_path: str) -> str:
    """Clean a CSV file path to create a valid dataset name.

    Args:
        csv_path: Path to CSV file, can include az:// prefix

    Returns:
        A cleaned string containing only alphanumeric characters, hyphens and underscores
    """
    csv_name = re.sub(
        "[^A-Za-z0-9-_]+", "", csv_path.lstrip("az://").rstrip(".csv").replace("/", "-")
    )
    return csv_name
