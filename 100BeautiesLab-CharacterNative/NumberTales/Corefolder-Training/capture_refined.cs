// Capture the actual refined VRMs with the same neutral lighting used for canonical models.
if(EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode)throw new System.Exception("Editor busy");
var scene=UnityEngine.SceneManagement.SceneManager.GetActiveScene();
if(scene.path!="Assets/100BeautiesLab-CharacterVRM/NumberTales/Refined/Corefolder-57-85-Refined.unity")throw new System.Exception("Expected refined review scene");
var cameraObject=new GameObject("Temporary Refined Capture Camera");var cam=cameraObject.AddComponent<Camera>();
cam.orthographic=true;cam.aspect=1;cam.cullingMask=1<<30;cam.backgroundColor=new Color(.75f,.75f,.75f,1);cam.clearFlags=CameraClearFlags.SolidColor;cam.nearClipPlane=.01f;cam.farClipPlane=20;cam.allowHDR=false;
var light=UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None).First(l=>l.type==LightType.Directional);var oldRot=light.transform.rotation;
var records=new System.Collections.Generic.List<object>();
foreach(var id in new[]{57,85}) {
 var root=GameObject.Find("Corefolder-"+id+" | refined MToon");
 var baked=new System.Collections.Generic.List<GameObject>();var b=new Bounds();bool first=true;
 foreach(var r in root.GetComponentsInChildren<SkinnedMeshRenderer>()) {
  var mesh=new Mesh();r.BakeMesh(mesh);var go=new GameObject("Temporary Refined Capture Mesh");go.layer=30;
  go.transform.SetPositionAndRotation(r.transform.position,r.transform.rotation);go.transform.localScale=r.transform.lossyScale;
  go.AddComponent<MeshFilter>().sharedMesh=mesh;var mr=go.AddComponent<MeshRenderer>();mr.sharedMaterials=r.sharedMaterials;
  if(first){b=mr.bounds;first=false;}else b.Encapsulate(mr.bounds);baked.Add(go);
 }
 cam.orthographicSize=Mathf.Max(b.size.y,Mathf.Max(b.size.x,b.size.z))*.56f;
 var dirs=new[]{Vector3.back,Vector3.left,Vector3.forward};var views=new[]{"front","side","back"};
 for(int i=0;i<3;i++) {
  cam.transform.position=b.center+dirs[i]*4;cam.transform.LookAt(b.center);light.transform.rotation=cam.transform.rotation*Quaternion.Euler(25,-25,0);
  var rt=new RenderTexture(1024,1024,24,RenderTextureFormat.ARGB32);var old=RenderTexture.active;cam.targetTexture=rt;
  try {cam.Render();cam.Render();RenderTexture.active=rt;var tex=new Texture2D(1024,1024,TextureFormat.RGB24,false);tex.ReadPixels(new Rect(0,0,1024,1024),0,0);tex.Apply();
   var path="100BeautiesLab-CharacterNative/NumberTales/Corefolder-"+id+"/Training/Refined-"+views[i]+".png";System.IO.File.WriteAllBytes(path,tex.EncodeToPNG());UnityEngine.Object.DestroyImmediate(tex);
   records.Add(new{id=id,view=views[i],path=path,orthographicSize=cam.orthographicSize,center=new[]{b.center.x,b.center.y,b.center.z},resolution=1024});
  } finally {cam.targetTexture=null;RenderTexture.active=old;rt.Release();UnityEngine.Object.DestroyImmediate(rt);}
 }
 foreach(var go in baked){UnityEngine.Object.DestroyImmediate(go.GetComponent<MeshFilter>().sharedMesh);UnityEngine.Object.DestroyImmediate(go);}
}
light.transform.rotation=oldRot;UnityEngine.Object.DestroyImmediate(cameraObject);
System.IO.File.WriteAllText("100BeautiesLab-CharacterNative/NumberTales/Corefolder-Training/targets/refined-captures.json",Newtonsoft.Json.JsonConvert.SerializeObject(records,Newtonsoft.Json.Formatting.Indented));
UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene);
return new{captures=records.Count};
