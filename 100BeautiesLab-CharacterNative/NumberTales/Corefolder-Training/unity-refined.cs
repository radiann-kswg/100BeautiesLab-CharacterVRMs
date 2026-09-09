if(EditorApplication.isCompiling || EditorApplication.isPlayingOrWillChangePlaymode) throw new System.Exception("Editor busy");
var current=UnityEngine.SceneManagement.SceneManager.GetActiveScene();
if(current.isDirty)throw new System.Exception("Preserve current unsaved scene first");
var folder="Assets/100BeautiesLab-CharacterVRM/NumberTales/Refined";
var path=folder+"/Corefolder-57-85-Refined.unity";
if(!AssetDatabase.IsValidFolder(folder))AssetDatabase.CreateFolder("Assets/100BeautiesLab-CharacterVRM/NumberTales","Refined");
if(AssetDatabase.LoadAssetAtPath<SceneAsset>(path)==null && !AssetDatabase.CopyAsset("Assets/100BeautiesLab-CharacterVRM/NumberTales/ModelingDraft/Corefolder-57-85-ModelingDraft.unity",path))throw new System.Exception("Scene copy failed");
var scene=UnityEditor.SceneManagement.EditorSceneManager.OpenScene(path,UnityEditor.SceneManagement.OpenSceneMode.Single);
foreach(var id in new[]{57,85}) {
    var old=GameObject.Find("Corefolder-"+id+" | refined MToon") ?? GameObject.Find("Corefolder-"+id+" | modeling draft");
    if(old!=null)UnityEngine.Object.DestroyImmediate(old);
    var modelPath="Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-"+id+"/Refined";
    var asset=AssetDatabase.LoadAssetAtPath<GameObject>(modelPath+"/Corefolder-"+id+"-Refined.vrm");
    if(asset==null)throw new System.Exception("Missing refined VRM");
    if(asset.GetComponentsInChildren<Renderer>(true).SelectMany(r=>r.sharedMaterials).Any(m=>!m.shader.name.Contains("MToon10")))throw new System.Exception("Expected all MToon materials");
    var root=(GameObject)PrefabUtility.InstantiatePrefab(asset,scene);
    root.name="Corefolder-"+id+" | refined MToon";
    foreach(var renderer in root.GetComponentsInChildren<SkinnedMeshRenderer>(true))renderer.updateWhenOffscreen=true;
    PrefabUtility.SaveAsPrefabAsset(root,modelPath+"/Corefolder-"+id+"-Refined.prefab");
    root.transform.position=new Vector3(id==57?-1.4f:1.4f,.03f,0);
    root.transform.rotation=Quaternion.Euler(0,180,0);
    var title=GameObject.Find(id+" title").GetComponent<TextMesh>();
    title.text=id+" | refined MToon\n"+(id==57?"7 tails / armband":"8 tails / pendant")+" | review required";
    title.transform.position=new Vector3(id==57?-1.4f:1.4f,1.5f,-.1f);
    var board=GameObject.Find(id+" official sheet - reference only");if(board!=null)board.transform.position=new Vector3(id==57?-1.4f:1.4f,2.55f,.2f);
}
Camera.main.transform.position=new Vector3(0,1.72f,-7);Camera.main.orthographicSize=2.12f;
foreach(var light in UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None)){light.color=Color.white;light.intensity=1;light.transform.rotation=Quaternion.Euler(25,335,0);}
RenderSettings.ambientMode=UnityEngine.Rendering.AmbientMode.Flat;RenderSettings.ambientLight=new Color(.6f,.6f,.6f);RenderSettings.fog=false;
UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene);AssetDatabase.SaveAssets();
return new{scene=scene.path};
