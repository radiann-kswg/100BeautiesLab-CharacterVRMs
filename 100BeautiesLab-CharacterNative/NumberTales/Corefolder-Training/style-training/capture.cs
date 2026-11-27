// Execute with OSS Unity MCP execute_code, after importing byte-identical Source-{id}.vrm copies.
// Uses a temporary scene; the original VRMs and their materials are not modified.
if(EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode)
    throw new System.Exception("Editor busy");
var scene=UnityEngine.SceneManagement.SceneManager.GetActiveScene();
if(scene.name!="Codex Style Capture") throw new System.Exception("Expected temporary capture scene");
var cam=GameObject.Find("StyleCaptureCamera").GetComponent<Camera>();
var light=GameObject.Find("StyleCaptureLight").GetComponent<Light>();
cam.backgroundColor=new Color(.75f,.75f,.75f,1f);
var test=GameObject.Find("CaptureBakeTest");
if(test!=null)UnityEngine.Object.DestroyImmediate(test);
var roots=scene.GetRootGameObjects().Where(o=>o.name.StartsWith("StyleSource-")).ToArray();
foreach(var root in roots)root.SetActive(false);
var records=new System.Collections.Generic.List<object>();
var folder="100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training/style-training/captures";
foreach(var id in new[]{4,16,20,22,25,93}) {
    var root=roots.Single(o=>o.name=="StyleSource-"+id);root.SetActive(true);
    var renderers=root.GetComponentsInChildren<SkinnedMeshRenderer>(true);
    var baked=new System.Collections.Generic.List<GameObject>();
    Bounds b=new Bounds();bool first=true;
    foreach(var r in renderers) {
        var mesh=new Mesh();r.BakeMesh(mesh);
        var obj=new GameObject("CaptureMesh-"+r.name);obj.transform.SetPositionAndRotation(r.transform.position,r.transform.rotation);
        obj.transform.localScale=r.transform.lossyScale;
        obj.AddComponent<MeshFilter>().sharedMesh=mesh;
        var mr=obj.AddComponent<MeshRenderer>();mr.sharedMaterials=r.sharedMaterials;
        if(first){b=mr.bounds;first=false;}else b.Encapsulate(mr.bounds);
        baked.Add(obj);r.enabled=false;
    }
    cam.orthographicSize=Mathf.Max(b.size.y,Mathf.Max(b.size.x,b.size.z))*.56f;
    cam.aspect=1f;
    var names=new[]{"front","side","back"};
    var dirs=new[]{Vector3.forward,Vector3.right,Vector3.back};
    for(int i=0;i<names.Length;i++) {
        cam.transform.position=b.center+dirs[i]*4f;cam.transform.LookAt(b.center);
        light.transform.rotation=cam.transform.rotation*Quaternion.Euler(25,-25,0);
        var rt=new RenderTexture(1024,1024,24,RenderTextureFormat.ARGB32);rt.antiAliasing=1;
        var old=RenderTexture.active;cam.targetTexture=rt;
        try {
            cam.Render();cam.Render();RenderTexture.active=rt;
            var tex=new Texture2D(1024,1024,TextureFormat.RGB24,false);
            tex.ReadPixels(new Rect(0,0,1024,1024),0,0);tex.Apply();
            var path=folder+"/Corefolder-"+id+"/"+names[i]+".png";
            System.IO.File.WriteAllBytes(path,tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
            records.Add(new {id=id,view=names[i],path=path,orthographicSize=cam.orthographicSize,center=new[]{b.center.x,b.center.y,b.center.z},cameraPosition=new[]{cam.transform.position.x,cam.transform.position.y,cam.transform.position.z},shader="VRM10/Universal Render Pipeline/MToon10",resolution=1024});
        } finally {cam.targetTexture=null;RenderTexture.active=old;rt.Release();UnityEngine.Object.DestroyImmediate(rt);}
    }
    foreach(var obj in baked){UnityEngine.Object.DestroyImmediate(obj.GetComponent<MeshFilter>().sharedMesh);UnityEngine.Object.DestroyImmediate(obj);}
    root.SetActive(false);
}
var json=Newtonsoft.Json.JsonConvert.SerializeObject(new {unity=Application.unityVersion,outlineRendererFeature="MToonOutlineRenderFeature",lightIntensity=light.intensity,ambientColor=new[]{.6f,.6f,.6f},background="neutral gray RGB 0.75",pose="source neutral",camera="orthographic; same scale for all views of each character",capture="temporary static BakeMesh snapshot; original shared MToon materials",images=records},Newtonsoft.Json.Formatting.Indented);
System.IO.File.WriteAllText(folder+"/capture-manifest.json",json);
return new {images=records.Count,manifest=folder+"/capture-manifest.json"};
