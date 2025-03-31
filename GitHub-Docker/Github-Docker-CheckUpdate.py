import os
import shutil
import subprocess
import docker

def check_for_updates(repo_path):
    # Store the current working directory
    prev_dir = os.getcwd()

    try:
        # Change directory to the repository path
        os.chdir(repo_path)

        # Fetch updates from the remote repository
        subprocess.run(["git", "fetch"])

        # Check if there are any updates available
        result = subprocess.run(["git", "status", "-uno"], capture_output=True, text=True)
        output = result.stdout

        # If "Your branch is behind" is in the output, updates are available
        if "Your branch is behind" in output:
            return True
        else:
            return False
    finally:
        # Change directory back to the previous one
        os.chdir(prev_dir)

def build_and_run_container(repo_url):
    repo_name = repo_url.split("/")[-1].split(".")[0]

    # Clone the repository if not already present
    if not os.path.exists(repo_name):
        subprocess.run(["git", "clone", repo_url])

    # Check for updates
    if check_for_updates(repo_name):
        print("Updates available. Building image and running container...")

        # Build Docker image
        work_directory = "/home/faghan/repos/GitHub-Docker"
        dockerfile_path = os.path.join(work_directory, "Dockerfile")
        image_name = "my_image1"
        subprocess.run(["docker", "build", "-t", image_name, "."])

        # Run Docker container
        container_name = "my_container_test1"
        client = docker.from_env()
        container = client.containers.run(image_name, detach=True, name=container_name)

        # Accessing the container (example: stop the container)
        # container.stop()

        print("Container is running.")
    else:
        print("No updates available.")

    # Clean up: Remove cloned repository
    if os.path.exists(repo_name):
        shutil.rmtree(repo_name)

if __name__ == "__main__":
    repository_url = "https://github.com/F-Gh2015/Nextflow-Pipeline"
    build_and_run_container(repository_url)
