# Services de Jarvis : bibliothèque standard Python seulement, aucun paquet ajouté.
# Une seule image pour les deux conteneurs : serveur.py (MCP interne) et web.py (interface).
FROM python:3.12-slim
WORKDIR /app
COPY serveur.py web.py qr.py politesse.py connexion.html connexion.js securite.html securite.js /app/
USER 65534:65534
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8710 8720
CMD ["python", "/app/serveur.py"]
