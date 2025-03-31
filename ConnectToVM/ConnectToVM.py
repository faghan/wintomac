import paramiko

# Azure VM details
vm_address = '172.205.169.175'
vm_username = 'azureuser'
private_key_path = '/home/faghan/.ssh/vm-fatemeh_key.pem'

# Establish SSH connection
ssh_client = paramiko.SSHClient()
ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Load the private key
private_key = paramiko.RSAKey.from_private_key_file(private_key_path)

try:
    # Connect to the VM
    ssh_client.connect(hostname=vm_address, username=vm_username, pkey=private_key)

    # Execute commands or interact with the VM
    stdin, stdout, stderr = ssh_client.exec_command('uname -a')
    print("Output:")
    for line in stdout:
        print(line.strip())

    # Close the SSH connection
    ssh_client.close()

except paramiko.AuthenticationException:
    print("Authentication failed, please check your credentials.")
except paramiko.SSHException as e:
    print("SSH connection failed:", str(e))
