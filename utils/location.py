# utils/location.py - Location and distance utilities
from math import radians, sin, cos, sqrt, atan2

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points on Earth using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def calculate_match_score(seeker, gig, distance):
    """
    Calculate weighted match score for gig recommendations
    Weights: skills 50%, availability 20%, distance 20%, ratings 10%
    """
    score = 0.0
    
    # Skills match (50%)
    if seeker['skills'] and gig['skills_required']:
        seeker_skills = set(seeker['skills'].lower().split(','))
        gig_skills = set(gig['skills_required'].lower().split(','))
        if gig_skills:
            skills_overlap = len(seeker_skills & gig_skills) / len(gig_skills)
            score += skills_overlap * 50
    else:
        # If no skills specified, give base score
        score += 25
    
    # Distance score (20%) - inversely proportional
    if distance <= 35:
        distance_score = 1 - (distance / 35)
        score += distance_score * 20
    
    # Availability (20%) - simplified for MVP
    if gig['status'] == 'open':
        score += 20
    
    # Rating score (10%)
    if seeker['rating'] > 0:
        rating_normalized = min(seeker['rating'] / 5.0, 1.0)
        score += rating_normalized * 10
    
    return min(round(score, 2), 100)  # Cap at 100