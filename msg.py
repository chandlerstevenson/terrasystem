from twilio.rest import Client

account_sid = 'AC6aeaaea30e46f0ecb32fe657ca79d1d8'
auth_token = '992e476301e544888716a8b67a43bc7f'
client = Client(account_sid, auth_token)

CHANDLER_NUMBER = "4047133808"
MICHAEL_NUMBER = "6787085808"
JAMIE_NUMBER = "9178610479"

message = client.messages.create(
  from_='+18889846584',
  body='Hello from Twilio',
  to=CHANDLER_NUMBER
)

print(message.sid)