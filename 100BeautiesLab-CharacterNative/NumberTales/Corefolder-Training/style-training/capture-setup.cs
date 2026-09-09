// Execute through OSS Unity MCP after source copies have been imported.
if(EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode)throw new System.Exception("Editor busy");
var old=UnityEngine.SceneManagement.SceneManager.GetActiveScene();
if(old.isDirty || string.IsNullOrEmpty(old.path))throw new System.Exception("Current scene must be saved and clean");
var previousPath=old.path;
foreach(var id in new[]{4,16,20,22,25,93}) {
 var asset=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/_CodexStyleCapture/Source-"+id+".vrm");
 if(asset==null || asset.GetComponentsInChildren<Renderer>(true).Any(r=>r.sharedMaterials.Any(m=>!m.shader.name.Contains("MToon10"))))throw new System.Exception("Expected imported MToon VRM: "+id);
}
var scene=UnityEditor.SceneManagement.EditorSceneManager.NewScene(UnityEditor.SceneManagement.NewSceneSetup.EmptyScene,UnityEditor.SceneManagement.NewSceneMode.Single);
scene.name="Codex Style Capture";
var cam=new GameObject("StyleCaptureCamera").AddComponent<Camera>();
cam.orthographic=true;cam.backgroundColor=new Color(.75f,.75f,.75f,1);cam.clearFlags=CameraClearFlags.SolidColor;
cam.nearClipPlane=.01f;cam.farClipPlane=30f;cam.allowHDR=false;cam.allowMSAA=false;
var light=new GameObject("StyleCaptureLight").AddComponent<Light>();light.type=LightType.Directional;light.intensity=1f;
RenderSettings.ambientMode=UnityEngine.Rendering.AmbientMode.Flat;RenderSettings.ambientLight=new Color(.6f,.6f,.6f);RenderSettings.fog=false;
foreach(var id in new[]{4,16,20,22,25,93}) {
 var asset=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/_CodexStyleCapture/Source-"+id+".vrm");
 var go=(GameObject)PrefabUtility.InstantiatePrefab(asset);go.name="StyleSource-"+id;
 go.transform.position=Vector3.zero;go.transform.rotation=Quaternion.identity;
 foreach(var r in go.GetComponentsInChildren<SkinnedMeshRenderer>(true))r.updateWhenOffscreen=true;
 go.SetActive(false);
}
return new {previousScene=previousPath,temporaryScene=scene.name};
