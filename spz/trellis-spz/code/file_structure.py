import os

def save_directory_structure(root_dir, output_file, depth=3):
    with open(output_file, "w", encoding="utf-8") as f:
        for root, dirs, files in os.walk(root_dir):
            level = root.replace(root_dir, "").count(os.sep)
            if level < depth:
                indent = " " * 4 * level
                f.write(f"{indent}{os.path.basename(root)}/\n")
                sub_indent = " " * 4 * (level + 1)
                for file in files:
                    f.write(f"{sub_indent}{file}\n")

# Set your root directory and output file
root_directory = "D:\ADAPT_AI\spz\\trellis-spz\code"  # Change this to the folder you want to scan
output_file = "folder_structure.txt"

# Run the function
save_directory_structure(root_directory, output_file)

print(f"Folder structure saved to {output_file}")
