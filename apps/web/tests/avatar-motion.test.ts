import {it,expect} from 'vitest';
import {avatarPose} from '../lib/avatar-motion';
it('animates speech and resets the mouth when playback stops',()=>{
 expect(avatarPose(1,'speaking',true).mouth).toBeGreaterThan(avatarPose(1,'idle',true).mouth);
 expect(avatarPose(2,'idle',true).mouth).toBe(0.08);
});
it('freezes when motion is disabled',()=>{
 expect(avatarPose(1,'speaking',false,0.5)).toEqual(avatarPose(20,'listening',false));
});
it('blinks briefly and ends a wave',()=>{
 expect(avatarPose(4.575,'idle',true).blink).toBeLessThan(0.1);
 expect(avatarPose(4,'idle',true).blink).toBe(1);
 expect(avatarPose(1,'idle',true,1).wave).toBeGreaterThan(0);
 expect(avatarPose(4,'idle',true,3).wave).toBe(0);
});
