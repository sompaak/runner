# Gemini VM Frontend

A web application that takes natural language instructions, uses Gemini to process them,
manages a GCP VM (creating it if necessary), and executes code on that VM via the
`sompaak/runner` service.
