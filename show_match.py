import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Load the CSV file into a pandas DataFrame
#data = pd.read_csv('score_data/match1_5_3_score_board.csv')
data = pd.read_csv('score_board.csv')
# Extract the time, ETF price, and account balance columns

teams = data['Team'].unique()
teams_data = [[x for x in data['ProfitOrLoss'][data['Team'] == team]] for team in teams]

bots = len(teams)
time = data['Time'][::bots]
price = data['EtfPrice'][::bots]/data['FuturePrice'][::bots]
position = [data['EtfPosition'][::bots],data['FuturePosition'][::bots]]


fig, (ax1, ax2, ax3) = plt.subplots(nrows=3, ncols=1, sharex=True)

# Create a line graph of ETF price over time
#plt.subplot(2, 1, 1)
ax1.plot(time, price)
ax1.set_title('Ratio and Balances')
ax1.set_ylabel('ETF:Future Ratio')


# # Create a subplot with two rows and one column


# # Plot the ETF/Future price ratio on the top subplot
# ax1.plot(time, price)
# ax1.set_title('ETF/Future Price Ratio and Buy Volume Over Time (Every Other Line)')
# ax1.set_ylabel('ETF/Future Price Ratio')

# # Create a bar graph of BuyVolume on the bottom subplot
# ax2.bar(time, buy_volume)
# ax2.set_xlabel('Time')
# ax2.set_ylabel('Buy Volume')

# Show the plot


# Create a line graph of account balance over time for each team
ax2.plot(2, 1, 2)
for i,team in enumerate(teams_data):
    #fix dimension
    if len(team) > len(time):
        diff = len(team) - len(time)
        team = team[:-diff]
    elif len(team) < len(time):
        diff = len(time) - len(team)
        team.extend([None]*diff)
     #plot   
    ax2.plot(time, team, label=teams[i])
ax3.plot(2,1,2)
ax3.plot(time, position[0], label = "etf")
ax3.plot(time, position[1], label = "future")
    
ax2.set_xlabel('Time')
ax2.set_ylabel('Account Balance')
plt.legend()

ax3.set_xlabel('time')
ax3.set_ylabel('positions')

plt.show()