# project
from project.director import Director

# Fill in from the Service Account and Project:
USERNAME   = 'btqs82b24t5g00b250a0'       # this is the key
PASSWORD   = '42079d7ddc3a479f82f615a95113da79'     # this is the secret
PROJECT_ID = 'btnlla14jplfdvvdrc60'                # this is the project id

# url base and endpoint
API_URL_BASE  = 'https://api.disruptive-technologies.com/v2'


if __name__ == '__main__':

    # initialise Director instance
    d = Director(USERNAME, PASSWORD, PROJECT_ID, API_URL_BASE)

    # iterate historic events
    d.run_history(plot=True)

    # stream
    d.run_stream()

