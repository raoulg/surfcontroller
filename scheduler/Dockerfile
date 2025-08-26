# scheduler/Dockerfile
FROM alpine:3.18

RUN apk add --no-cache bash curl jq 

# Set the working directory
WORKDIR /app

# Copy your scripts from the context's bash-scripts/ folder
COPY bash-scripts/*.sh ./

# Make the scripts executable
RUN chmod +x *.sh

# Copy the crontab file
COPY scheduler/crontab /etc/crontabs/root

# Command to start the cron daemon
CMD ["crond", "-f", "-l", "8"]
