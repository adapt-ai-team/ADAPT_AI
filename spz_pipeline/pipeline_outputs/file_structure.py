import os

def save_folder_structure(file_path, output_txt="folder_structure_trellis.txt"):
    if not os.path.isfile(file_path):
        print(f"'{file_path}' is not a valid file.")
        return

    abs_path = os.path.abspath(file_path)
    parts = abs_path.split(os.sep)

    lines = []
    for i, part in enumerate(parts):
        indent = '  ' * i
        lines.append(f"{indent}{part}")

    with open(output_txt, "w") as f:
        f.write("\n".join(lines))

    print(f"Folder structure saved to '{output_txt}'")

# Example usage
file_path = 'D:\ADAPT_AI\spz\\trellis-spz\code\example.py'  # Replace with your actual file path
save_folder_structure(file_path)
