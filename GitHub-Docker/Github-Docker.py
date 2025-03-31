import os
import shutil
import subprocess
import docker

# Clone the repository
# repo_url = "https://github.com/F-Gh2015/Nextflow-Pipeline"
# repo_name = repo_url.split("/")[-1].split(".")[0]
# if os.path.exists(repo_name):
#     shutil.rmtree(repo_name)
# subprocess.run(["git", "clone", repo_url])

# Build Docker image
work_directory = "/home/faghan/repos/GitHub-Docker"
dockerfile_path = os.path.join(work_directory, "Dockerfile")
image_name = "my_image"
subprocess.run(["docker", "build", "-t", image_name, "."])

# Run Docker container
container_name = "my_container_test"
client = docker.from_env()
container = client.containers.run(image_name, detach=True, name=container_name)

# Accessing the container (example: stop the container)
# container.stop()

# Clean up: Remove cloned repository
shutil.rmtree(repo_name)
