#!/usr/bin/python

import os
from json import JSONEncoder,JSONDecoder
from datetime import datetime,date,timedelta
from stravalib.strava import convert_datestr
from pytz import timezone
"""
Event data json format:
{
strava_id:
  {
  first_name: string
  last_name: string
  activities: 
    [{<strava_activity_id, int>:milage}]
  }
}
"""
class EventData:
  def __init__(self, file_name, start_date, end_date):
    self.__dataFile = file_name
    if os.path.isfile(file_name):
      fr = open(file_name)
      json_str = fr.read()
      if json_str is None or json_str == "":
        self.__data = {}
      else: self.__data = JSONDecoder().decode(json_str)
      fr.close()
    else:
      self.__data = {}
    self.__startDate = start_date
    self.__endDate = end_date
    self.numDays = 1+(self.__endDate-self.__startDate).days
    self.numWeeks = self.numDays/7
    self.pending_activities = {}
    self.rejected_activities = set()

  def add_athlete(self, first_name, last_name, athlete_id):
    """
    Add an athlete
    """
    if str(athlete_id) in self.__data: return
    entry = {'first_name': first_name,
             'last_name': last_name,
             'activities': [None for i in range(self.numDays)],
             'weekly_scores': [0 for i in range(self.numWeeks)]}
    self.__data[str(athlete_id)] = entry

  def register_athlete(self, first_name, last_name, strava_club_members):
    """
    Register an athlete to this event
    """
    for member in strava_club_members:
      if member['firstname'].strip().lower() == first_name.strip().lower() and \
           member['lastname'].strip().lower() == last_name.strip().lower():
        self.add_athlete(first_name.strip(), last_name.strip(), member['id'])
        return True
    return False

  def get_current_week_idx(self, time_zone='UTC'):
    today = datetime.now(timezone(time_zone)).date()
    ret = (today-self.__startDate).days/7
    return min(max(ret, 0), self.numWeeks)

  def update_weekly_scores(self, week_idx):
    """
    Calculate weekly score
    """
    if week_idx >= self.numWeeks: return
    for k,v in self.__data.iteritems():
      activities = v['activities']
      base_score = 0
      penalty = 0;
      drought = 0;
      for i in range(7):
        if activities[week_idx*7+i] is None:
          drought += 1;
        else: 
          base_score += 1
          if (drought > 0): penalty += (drought - 1);
          drought = 0;
      if (drought > 0): penalty += (drought - 1)
      score = min(max(base_score - penalty, 0), 6)
      v['weekly_scores'][week_idx] = score 

  def get_weekly_data(self, week_idx):
    ret = []
    if week_idx >= self.numWeeks or week_idx < 0: return ["Week:", []]
    week_start = self.__startDate + timedelta(week_idx*7)
    week_end = week_start + timedelta(6)
    week_str = 'Week: {0.month}/{0.day}/{0.year} - {1.month}/{1.day}/{1.year}'.format(week_start, week_end)
    for k,v in self.__data.iteritems():
      workouts = v['activities'][7*week_idx:7*week_idx+7]
      workouts_stats = []
      for x in workouts:
        if x:
          distance = 0.0
          for i,m in x.iteritems():
            distance += m
          workouts_stats.append("{0:.1f}".format(distance))
        else: workouts_stats.append('')
      entry = {'name': v['first_name'] + ' ' + v['last_name'],
               'workouts': workouts_stats, 
               'score': v['weekly_scores'][week_idx]}
      ret.append(entry)
    return [week_str, ret]

  def add_activity(self, strava_activity):
    """
    Add an activity
    """
    activity_id = strava_activity['id']
    if activity_id in self.rejected_activities:
      return False
    athlete_id = strava_activity['athlete']['id']
    gender = strava_activity['athlete']['sex']
    distance = strava_activity['distance']
    avg_pace = strava_activity['avg_pace']
    activity_date = strava_activity['start_date'].date()
    if activity_date > self.__endDate or activity_date < self.__startDate:
      return False
    if (gender == "M" and avg_pace > 11.0) or \
      (gender == "F" and avg_pace > 12.0) or \
      distance < 3.0:
      return False
    athlete = self.__data.get(str(athlete_id))
    if athlete is None: return False
    activities = athlete['activities']
    idx = (activity_date-self.__startDate).days
    if activities[idx] and str(activity_id) in activities[idx]:
      return False
    if strava_activity['manual']:
      print 'Found a manual activity!'
      self.pending_activities[str(activity_id)] = (str(athlete_id), idx, distance)
      return False
    if activities[idx] is None:
      activities[idx] = {str(activity_id): distance}
    else: activities[idx][str(activity_id)] = distance
    return True

  def approve_pending_activity(self, activity_id):
    activity = self.pending_activities.get(str(activity_id))  
    del self.pending_activities[str(activity_id)]
    if not activity: return False
    athlete,idx,distance = activity[0],activity[1],activity[2]
    athlete = self.__data.get(athlete)
    if athlete is None: return False
    activities = athlete['activities']
    activities[idx] = {str(activity_id): distance}

  def reject_pending_activity(self, activity_id):
    if str(activity_id) in self.pending_activities: 
      del self.pending_activities[str(activity_id)]
    self.rejected_activities.add(int(activity_id))

  def save_data(self):
    fr = open(self.__dataFile, 'w')
    fr.write(JSONEncoder().encode(self.__data))
    fr.close()
