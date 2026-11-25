using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UniVRM10;
using UnityEngine;

public static partial class CharacterReview
{
    [Serializable] class GazeSample
    {
        public int yaw;
        public float leftCentroidXmm, rightCentroidXmm, maxVertexTravelMm;
    }

    [Serializable] class GazeEvidence
    {
        public int leftEyeVertices, rightEyeVertices;
        public float returnErrorMm;
        public List<GazeSample> samples = new();
    }

    static void CheckGaze(Vrm10Instance model, SkinnedMeshRenderer[] skins, string dir, Input input)
    {
        var anim = model.GetComponent<Animator>();
        int[] Indices(SkinnedMeshRenderer skin, HumanBodyBones slot)
        {
            var bone = Array.IndexOf(skin.bones, anim.GetBoneTransform(slot));
            if (bone < 0) return Array.Empty<int>();
            return skin.sharedMesh.boneWeights.Select((w, i) => (w, i)).Where(p =>
                (p.w.boneIndex0 == bone && p.w.weight0 > .45f) || (p.w.boneIndex1 == bone && p.w.weight1 > .45f) ||
                (p.w.boneIndex2 == bone && p.w.weight2 > .45f) || (p.w.boneIndex3 == bone && p.w.weight3 > .45f))
                .Select(p => p.i).ToArray();
        }
        var ocular = skins.Select(r => (skin:r, left:Indices(r, HumanBodyBones.LeftEye),
            right:Indices(r, HumanBodyBones.RightEye))).OrderByDescending(x => Math.Min(x.left.Length, x.right.Length)).First();
        var left = ocular.left;
        var right = ocular.right;
        if (left.Length == 0 || right.Length == 0) throw new InvalidDataException("Missing weighted eye geometry");
        Vector3[] World() => Bake(ocular.skin).Select(ocular.skin.transform.TransformPoint).ToArray();
        var both = left.Concat(right).ToArray();
        var report = new GazeEvidence { leftEyeVertices=left.Length, rightEyeVertices=right.Length };
        var renderer = model.Runtime.LookAt;
        var previousInput = renderer.LookAtInput;
        renderer.SetYawPitchManually(0, 0);
        model.Runtime.Process();
        var neutral = World();
        var eyeBounds = new Bounds(neutral[both[0]], Vector3.zero);
        foreach (var i in both) eyeBounds.Encapsulate(neutral[i]);
        var center = eyeBounds.center + Vector3.down * .019f;
        var folder = Path.Combine(dir, "gaze");
        Directory.CreateDirectory(folder);
        Shoot(Path.Combine(folder, "front.png"), center, Vector3.forward, .30f);
        Shoot(Path.Combine(folder, "oblique.png"), center, Quaternion.Euler(0,20,0) * Vector3.forward, .30f);
        int artYaw = input.number switch { 6 => 9, 49 => -18, 57 => 27, 85 => 18, _ => 0 };
        if (artYaw != 0)
            Shoot(Path.Combine(folder, "art-angle.png"), center, Quaternion.Euler(0,artYaw,0) * Vector3.forward, .30f);
        foreach (var yaw in new[] {-12, 12})
        {
            renderer.SetYawPitchManually(yaw, 0);
            model.Runtime.Process();
            var pose = World();
            var sample = new GazeSample { yaw=yaw,
                leftCentroidXmm=1000*left.Average(i => pose[i].x-neutral[i].x),
                rightCentroidXmm=1000*right.Average(i => pose[i].x-neutral[i].x),
                maxVertexTravelMm=1000*both.Max(i => Vector3.Distance(pose[i], neutral[i])) };
            report.samples.Add(sample);
            Shoot(Path.Combine(folder, "yaw"+yaw+".png"), center, Vector3.forward, .30f);
            if (input.check && !(sample.leftCentroidXmm*sample.rightCentroidXmm > 0 && sample.maxVertexTravelMm > .1f))
                throw new InvalidDataException("Eye skins did not travel together: "+JsonUtility.ToJson(sample));
        }
        renderer.SetYawPitchManually(0, 0);
        model.Runtime.Process();
        var restored = World();
        report.returnErrorMm = 1000*both.Max(i => Vector3.Distance(restored[i], neutral[i]));
        if (input.check && report.returnErrorMm > .1f) throw new InvalidDataException("Eyes did not return to rest");
        renderer.LookAtInput = previousInput;
        model.Runtime.Process();
        File.WriteAllText(Path.Combine(folder, "gaze.json"), JsonUtility.ToJson(report, true));
    }
}
