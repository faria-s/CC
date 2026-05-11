# Repositório CC 25/26

## Grade: 17.8/20 :star:

### Authors

 - Nuno Peixoto   (A93244)
 - Luís Ferreira  (A98286)
 - Salomé Faria   (A108487)

# Setup

Start by cloning this repository, and creating a Python virtual environment:

```
$ git@github.com:faria-s/CC.git
$ python -m venv .venv
```

To run the project, start by running:

```
$ source .venv/bin/activate
```

To run the server and the agent, run, respectively:

```
$ python -m mothership_server <missions_json> <database>
$ python -m rover <server_ip>
$ python -m ground_control <server_ip> [api_port]
