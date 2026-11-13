# Static web page served by an unprivileged nginx on port 8080.
# Built by the platform's golden-path workflow - version.txt is written by CI.
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY . /usr/share/nginx/html/
EXPOSE 8080
