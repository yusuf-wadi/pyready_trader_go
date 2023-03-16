import pandas as pd

fat_data = pd.read_csv("data/market_data1.csv")

data_tick = 0

a_frame = fat_data[fat_data['Instrument'] == 0][::2]
b_frame = fat_data[fat_data['Instrument'] == 1][::2]


combined_df = pd.concat([a_frame,b_frame])
sorted_df = combined_df.sort_values('Time')

sorted_df.to_csv("diet_data/data_1.csv", index=False)
            