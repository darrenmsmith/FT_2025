"""
Bridge Layer - Connects Field Trainer runs to Athletic Training Platform
Automatically processes completed runs and extracts performance metrics
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from models_extended import ExtendedDatabaseManager


class PerformanceBridge:
    """Bridges existing field trainer data to athletic training platform"""
    
    def __init__(self, db_manager: ExtendedDatabaseManager, existing_db_manager):
        """
        Args:
            db_manager: Extended database manager (new features)
            existing_db_manager: Your existing DatabaseManager from db_manager.py
        """
        self.ext_db = db_manager
        self.db = existing_db_manager
        
        # Map course names to metric names
        self.course_metrics = {
            'Pro Agility': 'pro_agility',
            '40 Yard Dash': '40_yard_dash',
            'L-Drill': 'l_drill',
            'Three Cone Drill': 'three_cone',
            'Shuttle Run': 'shuttle_run',
            # Add more courses as you create them
        }
        
        # Achievement thresholds
        self.achievement_criteria = {
            'speed_demon': {
                'pro_agility': 4.0,      # Under 4.0 seconds
                '40_yard_dash': 4.5,     # Under 4.5 seconds
                'l_drill': 7.0,          # Under 7.0 seconds
            },
            'improvement_star': {
                'improvement_percentage': 5.0  # 5% improvement from previous PR
            }
        }
    
    def process_completed_run(self, run_id: str) -> Dict[str, Any]:
        """
        Process a completed run - extract metrics, detect PRs, award achievements
        
        Returns: {
            'metrics_recorded': int,
            'is_new_pr': bool,
            'achievements_awarded': List[str],
            'performance_summary': Dict
        }
        """
        print(f"\n{'='*80}")
        print(f"🔄 BRIDGE: Processing completed run {run_id[:8]}...")
        
        # Get run data
        run = self.db.get_run(run_id)
        if not run:
            print(f"   ❌ Run not found")
            return {'error': 'Run not found'}
        
        athlete_id = run['athlete_id']
        course_id = run['course_id']
        total_time = run['total_time']
        
        # Get course info
        course = self.db.get_course(course_id)
        if not course:
            print(f"   ❌ Course not found")
            return {'error': 'Course not found'}
        
        course_name = course['course_name']
        athlete_name = run.get('athlete_name', 'Unknown')
        
        print(f"   Course: {course_name}")
        print(f"   Athlete: {athlete_name}")
        print(f"   Total Time: {total_time:.3f}s")
        
        # Map course to metric
        metric_name = self.course_metrics.get(course_name, 
                                             course_name.lower().replace(' ', '_'))
        
        # Get segment times
        segments = self.db.get_run_segments(run_id)
        segment_data = []
        
        print(f"\n   📊 Segment Analysis:")
        for seg in segments:
            if seg.get('actual_time'):
                segment_data.append({
                    'from_device': seg['from_device'],
                    'to_device': seg['to_device'],
                    'time': seg['actual_time'],
                    'sequence': seg['sequence']
                })
                print(f"      Segment {seg['sequence']}: {seg['actual_time']:.3f}s")
        
        # Record overall performance
        print(f"\n   💾 Recording performance...")
        record_id, is_pr = self.ext_db.record_performance(
            athlete_id=athlete_id,
            metric_name=metric_name,
            metric_value=total_time,
            metric_unit='seconds',
            run_id=run_id,
            session_id=run.get('session_id'),
            course_id=course_id,
            segment_data=segment_data
        )
        
        print(f"      ✅ Performance recorded (ID: {record_id[:8]}...)")
        
        result = {
            'metrics_recorded': 1 + len(segment_data),
            'is_new_pr': is_pr,
            'achievements_awarded': [],
            'performance_summary': {
                'metric_name': metric_name,
                'total_time': total_time,
                'segments': segment_data
            }
        }
        
        # If new PR, celebrate!
        if is_pr:
            print(f"\n   🏆 NEW PERSONAL RECORD!")
            
            # Get PR details
            prs = self.ext_db.get_athlete_prs(athlete_id)
            current_pr = next((pr for pr in prs if pr['metric_name'] == metric_name), None)
            
            if current_pr and current_pr.get('previous_best'):
                improvement = current_pr['previous_best'] - total_time
                percentage = (improvement / current_pr['previous_best']) * 100
                print(f"      Previous: {current_pr['previous_best']:.3f}s")
                print(f"      New: {total_time:.3f}s")
                print(f"      Improvement: {improvement:.3f}s ({percentage:.1f}%)")
                
                # Check for improvement achievement
                if percentage >= self.achievement_criteria['improvement_star']['improvement_percentage']:
                    achievement_id = self.ext_db.award_achievement(
                        athlete_id=athlete_id,
                        badge_type='improvement_star',
                        badge_name='Improvement Star',
                        description=f'Improved {metric_name.replace("_", " ").title()} by {percentage:.1f}%',
                        criteria=f'Achieved {percentage:.1f}% improvement',
                        run_id=run_id,
                        metric_value=total_time
                    )
                    result['achievements_awarded'].append('improvement_star')
                    print(f"      ⭐ ACHIEVEMENT UNLOCKED: Improvement Star!")
        
        # Check for absolute performance achievements
        speed_threshold = self.achievement_criteria['speed_demon'].get(metric_name)
        if speed_threshold and total_time < speed_threshold:
            # Check if they already have this badge
            existing = self.ext_db.get_athlete_achievements(athlete_id)
            has_badge = any(
                a['badge_type'] == 'speed_demon' and 
                metric_name in a.get('criteria', '')
                for a in existing
            )
            
            if not has_badge:
                achievement_id = self.ext_db.award_achievement(
                    athlete_id=athlete_id,
                    badge_type='speed_demon',
                    badge_name='Speed Demon',
                    description=f'Achieved elite time in {metric_name.replace("_", " ").title()}',
                    criteria=f'Under {speed_threshold}s in {metric_name}',
                    run_id=run_id,
                    metric_value=total_time
                )
                result['achievements_awarded'].append('speed_demon')
                print(f"      ⚡ ACHIEVEMENT UNLOCKED: Speed Demon!")
        
        print(f"{'='*80}\n")
        return result
    
    def get_athlete_dashboard_stats(self, athlete_id: str) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics for athlete"""
        
        # Get performance history
        perf_history = self.ext_db.get_athlete_performance_history(athlete_id, limit=50)
        
        # Get PRs
        prs = self.ext_db.get_athlete_prs(athlete_id)
        
        # Get achievements
        achievements = self.ext_db.get_athlete_achievements(athlete_id)
        
        # Calculate trends
        metrics = {}
        for perf in perf_history:
            metric = perf['metric_name']
            if metric not in metrics:
                metrics[metric] = []
            metrics[metric].append(perf['metric_value'])
        
        trends = {}
        for metric, values in metrics.items():
            if len(values) >= 2:
                first = values[-1]  # Oldest
                latest = values[0]  # Newest
                improvement = first - latest
                percentage = (improvement / first) * 100 if first > 0 else 0
                
                trends[metric] = {
                    'first_value': first,
                    'latest_value': latest,
                    'improvement': improvement,
                    'improvement_percentage': percentage,
                    'total_attempts': len(values)
                }
        
        return {
            'athlete_id': athlete_id,
            'statistics': {
                'total_runs': len(perf_history),
                'total_prs': len(prs),
                'total_achievements': len(achievements),
            },
            'personal_records': prs,
            'recent_performance': perf_history[:10],
            'trends': trends,
            'achievements': achievements
        }
    
    def get_team_rankings(self, team_id: str, metric_name: str) -> List[Dict]:
        """Calculate team rankings for a specific metric"""
        
        # Get all athletes on team
        athletes = self.db.get_athletes_by_team(team_id)
        
        rankings = []
        for athlete in athletes:
            athlete_id = athlete['athlete_id']
            
            # Get their PR for this metric
            prs = self.ext_db.get_athlete_prs(athlete_id)
            pr = next((p for p in prs if p['metric_name'] == metric_name), None)
            
            if pr:
                rankings.append({
                    'athlete_id': athlete_id,
                    'athlete_name': athlete['name'],
                    'jersey_number': athlete.get('jersey_number'),
                    'best_time': pr['current_best'],
                    'achieved_at': pr['achieved_at']
                })
        
        # Sort by best time (ascending)
        rankings.sort(key=lambda x: x['best_time'])
        
        # Add rank
        for idx, ranking in enumerate(rankings, 1):
            ranking['rank'] = idx
        
        return rankings


class TouchEventBridge:
    """Hooks into existing touch event system"""
    
    def __init__(self, performance_bridge: PerformanceBridge):
        self.bridge = performance_bridge
    
    def on_run_completed(self, run_id: str):
        """Called when a run is completed"""
        try:
            result = self.bridge.process_completed_run(run_id)
            return result
        except Exception as e:
            print(f"❌ Error processing performance: {e}")
            import traceback
            traceback.print_exc()
            return None


def initialize_bridge(existing_db_manager):
    """
    Initialize the bridge layer
    
    Usage in coach_interface.py:
        from bridge_layer import initialize_bridge
        perf_bridge, touch_bridge = initialize_bridge(db)
    """
    ext_db = ExtendedDatabaseManager('/opt/data/field_trainer.db')
    perf_bridge = PerformanceBridge(ext_db, existing_db_manager)
    touch_bridge = TouchEventBridge(perf_bridge)
    
    print("✅ Performance bridge initialized")
    return perf_bridge, touch_bridge


if __name__ == '__main__':
    print("Bridge Layer Module - Import this in coach_interface.py")
