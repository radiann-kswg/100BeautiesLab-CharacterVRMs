using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UniVRM10;
using Object = UnityEngine.Object;

public static class CharacterReview
{
    [Serializable] public class Input { public int number; public string asset; public string sha256; public bool check; public bool artwork; public bool mouth; }
    [Serializable] public class Plan { public string output; public Input[] models; }
    [Serializable] public class Motion { public string chain; public int joints, weightedVertices; public float peakTipMeters, peakSkinMeters, finalTipMeters; }
    [Serializable] public class Face { public string expression; public float maxVertexMeters; }
    [Serializable] public class Result
    {
        public int number; public string sha256, unity, shader, colorSpace, renderPipeline;
        public int meshes, humanoidBones, colliderGroups;
        public bool playMode, validHumanoid;
        public float orthographicSize;
        public List<Face> expressions = new(); public List<Motion> springs = new();
    }
    const string Active = "Corefolder.CharacterReview";
    const float Dt = 1f / 60f;
    static string Project => Directory.GetParent(Application.dataPath).FullName;
    static Camera camera;
    static Light illumination;
    static SkinnedMeshRenderer[] visibleSkins;

    public static void Start()
    {
        SessionState.SetBool(Active, true);
        EditorApplication.EnterPlaymode();
    }

    [InitializeOnLoadMethod]
    static void Install() => EditorApplication.update += CheckReady;

    static void CheckReady()
    {
        if (SessionState.GetBool(Active, false) && Application.isPlaying && !EditorApplication.isCompiling && !EditorApplication.isUpdating)
            Run();
    }

    static void Run()
    {
        SessionState.SetBool(Active, false);
        try
        {
            if (!Application.isPlaying) throw new Exception("Play Mode was not entered");
            var plan = JsonUtility.FromJson<Plan>(File.ReadAllText(Path.Combine(Project, "character-review.json")));
            foreach (var l in Object.FindObjectsByType<Light>(FindObjectsSortMode.None)) l.enabled = false;
            camera = new GameObject("Review Camera").AddComponent<Camera>();
            camera.enabled = false; camera.orthographic = true; camera.aspect = 1;
            camera.nearClipPlane = .01f; camera.farClipPlane = 30; camera.allowHDR = false; camera.allowMSAA = false;
            camera.backgroundColor = new Color(.75f,.75f,.75f,1); camera.clearFlags = CameraClearFlags.SolidColor;
            illumination = new GameObject("Review Light").AddComponent<Light>();
            illumination.type = LightType.Directional; illumination.intensity = 1;
            RenderSettings.ambientMode = AmbientMode.Flat; RenderSettings.ambientLight = new Color(.6f,.6f,.6f); RenderSettings.fog = false;
            foreach (var input in plan.models) Review(input, plan.output);
            EditorApplication.Exit(0);
        }
        catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(2); }
    }

    static Vector3[] Bake(SkinnedMeshRenderer renderer)
    {
        var mesh = new Mesh();
        try { renderer.BakeMesh(mesh); return mesh.vertices; }
        finally { Object.DestroyImmediate(mesh); }
    }

    static void Shoot(string path, Vector3 center, Vector3 direction, float halfSize)
    {
        camera.orthographicSize = halfSize;
        camera.transform.position = center + direction * 4; camera.transform.LookAt(center);
        illumination.transform.rotation = camera.transform.rotation * Quaternion.Euler(25,-25,0);
        var rt = RenderTexture.GetTemporary(900,900,24,RenderTextureFormat.ARGB32);
        var previous = RenderTexture.active;
        var snapshots = new List<(SkinnedMeshRenderer original, GameObject holder, Mesh mesh)>();
        var texture = new Texture2D(900,900,TextureFormat.RGB24,false);
        try
        {
            // Multiple samples in one Play Mode frame need freshly baked GPU-visible geometry.
            foreach (var r in visibleSkins)
            {
                var mesh = new Mesh(); r.BakeMesh(mesh);
                var holder = new GameObject("Snapshot "+r.name);
                holder.transform.SetPositionAndRotation(r.transform.position, r.transform.rotation);
                holder.transform.localScale = r.transform.lossyScale;
                holder.AddComponent<MeshFilter>().sharedMesh = mesh;
                holder.AddComponent<MeshRenderer>().sharedMaterials = r.sharedMaterials;
                snapshots.Add((r,holder,mesh)); r.enabled = false;
            }
            camera.targetTexture = rt;
            camera.Render(); camera.Render();
            RenderTexture.active = rt;
            texture.ReadPixels(new Rect(0,0,900,900),0,0); texture.Apply();
            File.WriteAllBytes(path, texture.EncodeToPNG());
        }
        finally
        {
            camera.targetTexture = null; RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(rt); Object.DestroyImmediate(texture);
            foreach (var sample in snapshots)
            {
                Object.DestroyImmediate(sample.holder); Object.DestroyImmediate(sample.mesh);
                sample.original.enabled = true;
            }
        }
    }

    static void Review(Input input, string output)
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(input.asset);
        if (!prefab) throw new Exception("VRM importer did not produce prefab: " + input.asset);
        var obj = Object.Instantiate(prefab);
        try
        {
            var model = obj.GetComponent<Vrm10Instance>();
            var animator = obj.GetComponent<Animator>();
            var skins = obj.GetComponentsInChildren<SkinnedMeshRenderer>();
            visibleSkins = skins;
            if (skins.Length == 0 || !model || !animator || !animator.avatar.isValid || !animator.avatar.isHuman)
                throw new Exception("VRM instance, skin or humanoid missing: " + input.asset);
            foreach (var r in skins) r.updateWhenOffscreen = true;
            var shaders = skins.SelectMany(r => r.sharedMaterials).Select(m => m.shader.name).Distinct().ToArray();
            if (shaders.Any(s => !s.Contains("Universal Render Pipeline/MToon10"))) throw new Exception("Unexpected shaders: " + string.Join(", ", shaders));
            var stats = new Result { number = input.number, sha256 = input.sha256, unity = Application.unityVersion,
                shader = string.Join(", ", shaders), meshes = skins.Length, validHumanoid = animator.avatar.isValid && animator.avatar.isHuman,
                playMode = Application.isPlaying, humanoidBones = Enumerable.Range(0,(int)HumanBodyBones.LastBone).Count(i=>animator.GetBoneTransform((HumanBodyBones)i)),
                colorSpace = QualitySettings.activeColorSpace.ToString(), renderPipeline = GraphicsSettings.currentRenderPipeline.name, orthographicSize = .88f,
                colliderGroups = model.SpringBone.ColliderGroups.Count };
            var dir = Path.Combine(output,"Corefolder-"+input.number); Directory.CreateDirectory(dir);
            var points = skins.SelectMany(r => Bake(r).Select(r.transform.TransformPoint)).ToArray();
            var bounds = new Bounds(points[0], Vector3.zero);
            foreach (var point in points) bounds.Encapsulate(point);
            if (bounds.extents.x >= stats.orthographicSize || bounds.extents.z >= stats.orthographicSize || bounds.extents.y >= stats.orthographicSize)
                throw new Exception("Camera clips #" + input.number + ", bounds " + bounds);
            foreach (var view in new[]{("front",Vector3.forward),("side",Vector3.right),("back",Vector3.back)})
                Shoot(Path.Combine(dir,view.Item1+".png"),bounds.center,view.Item2,stats.orthographicSize);
            if(input.mouth) CheckMouth(model,skins,stats,dir);
            if (input.artwork)
            {
                foreach(int degree in new[]{-36,-27,-18,-9,0,9,18,27,36})
                    Shoot(Path.Combine(dir,"angle"+degree+".png"),bounds.center,Quaternion.Euler(0,degree,0)*Vector3.forward,stats.orthographicSize);
                var tails = skins.Where(r=>r.name.IndexOf("Tail",StringComparison.OrdinalIgnoreCase)>=0 && r.name.IndexOf("ponytail",StringComparison.OrdinalIgnoreCase)<0).ToArray();
                if(tails.Length==0) throw new Exception("No tail meshes found: "+string.Join(", ",skins.Select(r=>r.name)));
                var hidden = skins.Except(tails).ToArray();
                foreach(var r in hidden) r.enabled=false;
                visibleSkins=tails;
                Shoot(Path.Combine(dir,"atlas.png"),bounds.center,Vector3.back,stats.orthographicSize);
                visibleSkins=skins;
                foreach(var r in hidden) r.enabled=true;
            }
            if (input.check)
            {
                CheckFace(model, skins, stats, dir, bounds.center);
                CheckSprings(model, skins, stats, dir, bounds.center);
            }
            File.WriteAllText(Path.Combine(dir,"unity.json"),JsonUtility.ToJson(stats,true));
            Debug.Log("REVIEW COMPLETE #" + input.number + " expressions=" + stats.expressions.Count + " springs=" + stats.springs.Count);
        }
        finally { Object.DestroyImmediate(obj); }
    }

    static void CheckFace(Vrm10Instance model, SkinnedMeshRenderer[] skins, Result stats, string dir, Vector3 center)
    {
        var faces = skins.Where(r=>r.sharedMesh.blendShapeCount>0).ToArray();
        foreach (var item in model.Vrm.Expression.Clips.Where(x=>x.Clip.MorphTargetBindings.Length>0))
        {
            var key = model.Vrm.Expression.CreateKey(item.Clip);
            var before = faces.Select(Bake).ToArray();
            model.Runtime.Expression.SetWeight(key,1); model.Runtime.Process();
            var delta = faces.Select((r,i) => Bake(r).Zip(before[i],Vector3.Distance).Max()).Max();
            if (!(delta > .0001f)) throw new Exception("No facial deformation for " + key);
            stats.expressions.Add(new Face {expression = key.Name, maxVertexMeters = delta});
            if (new[]{ExpressionKey.Blink,ExpressionKey.Aa,ExpressionKey.Happy}.Contains(key))
                Shoot(Path.Combine(dir,key.Name+".png"),center,Vector3.forward,stats.orthographicSize);
            model.Runtime.Expression.SetWeight(key,0); model.Runtime.Process();
        }
        if(stats.expressions.Count < 13) throw new Exception("Missing bound expressions");
    }

    [Serializable] public class Sample { public string pose; public float maxDeltaMeters; }
    [Serializable] public class JointSample { public string bone; public float maxLipTravelMeters, maxRigidErrorMeters; }
    [Serializable] public class MouthResult
    {
        public string sha256;
        public bool jawMapped;
        public int lipProbeVertices;
        public float neutralReturnMeters;
        public List<Sample> expressions = new();
        public List<JointSample> joints = new();
    }

    static void CheckMouth(Vrm10Instance model, SkinnedMeshRenderer[] skins, Result stats, string dir)
    {
        var faces=skins.Where(r=>r.sharedMesh.blendShapeCount>0).ToArray();
        Vector3[] WorldFace() => faces.SelectMany(r=>Bake(r).Select(r.transform.TransformPoint)).ToArray();
        var anim=model.GetComponent<Animator>();
        var expression=model.Runtime.Expression;
        var keys=expression.ExpressionKeys.ToArray();
        model.Runtime.Process();
        var neutral=WorldFace();
        var mouthDir=Path.Combine(dir,"mouth");Directory.CreateDirectory(mouthDir);
        var result=new MouthResult{sha256=stats.sha256,jawMapped=anim.GetBoneTransform(HumanBodyBones.Jaw)!=null};
        var active=new List<int>();
        if(keys.Contains(ExpressionKey.Aa))
        {
            expression.SetWeight(ExpressionKey.Aa,1);model.Runtime.Process();
            var open=WorldFace();
            for(int i=0;i<neutral.Length;i++) if(Vector3.Distance(neutral[i],open[i])>.002f) active.Add(i);
            expression.SetWeight(ExpressionKey.Aa,0);model.Runtime.Process();
        }
        result.lipProbeVertices=active.Count;
        Vector3 center;
        if(active.Count>0)
        {
            var mouthBounds=new Bounds(neutral[active[0]],Vector3.zero);
            foreach(var i in active) mouthBounds.Encapsulate(neutral[i]);
            center=mouthBounds.center;
        }
        else center=anim.GetBoneTransform(HumanBodyBones.Head).position + new Vector3(0,.11f,.10f);
        // Include the eyes and chin at an identical real-world scale for reference and production VRMs.
        Vector3 cropCenter=center+Vector3.up*.065f;
        var angle=Quaternion.Euler(0,25,0)*Vector3.forward;
        Shoot(Path.Combine(mouthDir,"neutral-front.png"),cropCenter,Vector3.forward,.205f);
        Shoot(Path.Combine(mouthDir,"neutral-oblique.png"),cropCenter,angle,.205f);
        Shoot(Path.Combine(mouthDir,"neutral-profile.png"),cropCenter,Vector3.right,.205f);
        var combos=new[]{("aa-025",ExpressionKey.Aa,.25f,false),("aa-050",ExpressionKey.Aa,.5f,false),
            ("aa-075",ExpressionKey.Aa,.75f,false),("aa-100",ExpressionKey.Aa,1f,false),
            ("ih-050",ExpressionKey.Ih,.5f,false),("ou-050",ExpressionKey.Ou,.5f,false),
            ("ee-050",ExpressionKey.Ee,.5f,false),("oh-050",ExpressionKey.Oh,.5f,false),
            ("blink-aa",ExpressionKey.Aa,.5f,true)};
        foreach(var (label,key,weight,blink) in combos)
        {
            if(!keys.Contains(key)) continue;
            expression.SetWeight(key,weight);
            if(blink)expression.SetWeight(ExpressionKey.Blink,1);
            model.Runtime.Process();var posed=WorldFace();
            float distance=active.Select(i=>Vector3.Distance(neutral[i],posed[i])).DefaultIfEmpty(0f).Max();
            result.expressions.Add(new Sample {pose=label,maxDeltaMeters=distance});
            Shoot(Path.Combine(mouthDir,label+".png"),cropCenter,Vector3.forward,.205f);
            if(label=="aa-050")Shoot(Path.Combine(mouthDir,"aa-050-oblique.png"),cropCenter,angle,.205f);
            expression.SetWeight(key,0);
            if(blink)expression.SetWeight(ExpressionKey.Blink,0);
            model.Runtime.Process();
        }
        foreach(var pair in new[]{(HumanBodyBones.Head,new Vector3(0,12,0)),(HumanBodyBones.Neck,new Vector3(-8,0,0))})
        {
            if(active.Count==0)break;
            var joint=anim.GetBoneTransform(pair.Item1);if(!joint)continue;
            var target=anim.GetBoneTransform(HumanBodyBones.Head);
            var inverse=target.worldToLocalMatrix;
            var rot=joint.localRotation;
            joint.localRotation=rot*Quaternion.Euler(pair.Item2);
            model.Runtime.Process();
            var posed=WorldFace();var delta=target.localToWorldMatrix*inverse;
            result.joints.Add(new JointSample {bone=pair.Item1.ToString(),
                maxLipTravelMeters=active.Max(i=>Vector3.Distance(neutral[i],posed[i])),
                maxRigidErrorMeters=active.Max(i=>Vector3.Distance(delta.MultiplyPoint3x4(neutral[i]),posed[i]))});
            if(pair.Item1==HumanBodyBones.Head && keys.Contains(ExpressionKey.Aa))
            {
                expression.SetWeight(ExpressionKey.Aa,.65f);model.Runtime.Process();
                Shoot(Path.Combine(mouthDir,"head-turn-speaking.png"),cropCenter,angle,.205f);
                expression.SetWeight(ExpressionKey.Aa,0);model.Runtime.Process();
            }
            joint.localRotation=rot;model.Runtime.Process();
        }
        var restored=WorldFace();
        result.neutralReturnMeters=active.Select(i=>Vector3.Distance(neutral[i],restored[i])).DefaultIfEmpty(0f).Max();
        File.WriteAllText(Path.Combine(mouthDir,"rig.json"),JsonUtility.ToJson(result,true));
    }

    sealed class Probe
    {
        public Transform parent, tip;
        public Vector3 rest;
        public Motion stats;
        public Dictionary<SkinnedMeshRenderer,int[]> vertices = new();
    }

    static void CheckSprings(Vrm10Instance model, SkinnedMeshRenderer[] skins, Result stats, string dir, Vector3 center)
    {
        var runtime = model.Runtime.SpringBone;
        if (!(runtime is Vrm10FastSpringboneRuntimeStandalone)) throw new Exception("Expected prefab FastSpringBone runtime");
        for(int i=0;i<120;i++) runtime.Process(Dt);
        var atRest = skins.ToDictionary(r=>r, Bake);
        var probes = new List<Probe>();
        foreach (var group in model.SpringBone.Springs)
        {
            var chain = group.Joints.Select(j=>j.transform).ToArray();
            if (chain.Length<2) throw new Exception("Empty or unarticulated spring "+group.Name);
            var p = new Probe { parent=chain[0].parent, tip=chain.Last(),
                stats=new Motion { chain=chain[0].name, joints=chain.Length } };
            p.rest = p.parent.InverseTransformPoint(p.tip.position);
            foreach (var r in skins)
            {
                var mapped = r.bones.Select((bone,i)=>(bone,i)).Where(t=>chain.Contains(t.bone)).Select(t=>t.i).ToHashSet();
                if(mapped.Count==0) continue;
                var weights=r.sharedMesh.boneWeights;
                var affected = Enumerable.Range(0,weights.Length).Where(i=>{
                    var w=weights[i];
                    return (w.weight0>.05f && mapped.Contains(w.boneIndex0)) || (w.weight1>.05f && mapped.Contains(w.boneIndex1)) ||
                           (w.weight2>.05f && mapped.Contains(w.boneIndex2)) || (w.weight3>.05f && mapped.Contains(w.boneIndex3));
                }).ToArray();
                if(affected.Length>0) { p.vertices.Add(r,affected); p.stats.weightedVertices+=affected.Length; }
            }
            probes.Add(p); stats.springs.Add(p.stats);
        }
        if(probes.Count==0) throw new Exception("Missing springs");
        var root = model.transform;
        var angle = new Vector3(.42f, .08f, -1).normalized;
        string frames = Path.Combine(dir,"motion"); Directory.CreateDirectory(frames);
        Shoot(Path.Combine(frames,"000.png"),center,angle,stats.orthographicSize);
        for (int frame=1;frame<=150;frame++)
        {
            float travel=frame<=24?Mathf.Sin(frame * Mathf.PI / 12f):0;
            root.localPosition=new Vector3(.09f*travel,0,.03f*travel);
            runtime.Process(Dt);
            if ((frame<=48 && frame%2==0) || frame==90)
                Shoot(Path.Combine(frames,frame.ToString("D3")+".png"),center+root.localPosition,angle,stats.orthographicSize);
            var sampled=frame<=36?atRest.Keys.ToDictionary(r=>r,Bake):null;
            foreach(var p in probes)
            {
                float tip=Vector3.Distance(p.rest,p.parent.InverseTransformPoint(p.tip.position));
                p.stats.peakTipMeters=Mathf.Max(p.stats.peakTipMeters,tip); p.stats.finalTipMeters=tip;
                if(sampled==null) continue;
                foreach(var pair in p.vertices)
                {
                    var r=pair.Key;
                    foreach(int i in pair.Value)
                        p.stats.peakSkinMeters=Mathf.Max(p.stats.peakSkinMeters,r.transform.TransformVector(sampled[r][i]-atRest[r][i]).magnitude);
                }
            }
        }
        foreach(var p in probes)
            if (!(p.stats.peakTipMeters>.0001f && p.stats.peakSkinMeters>.0001f && p.stats.finalTipMeters<p.stats.peakTipMeters*.65f))
                throw new Exception("Spring motion or recovery failed: "+JsonUtility.ToJson(p.stats));
    }
}
