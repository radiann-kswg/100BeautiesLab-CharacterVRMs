if(EditorApplication.isCompiling || EditorApplication.isPlayingOrWillChangePlaymode) throw new System.Exception("Editor busy");
var current=UnityEngine.SceneManagement.SceneManager.GetActiveScene();
if(current.isDirty)throw new System.Exception("Preserve current unsaved scene first");
var folder="Assets/100BeautiesLab-CharacterVRM/NumberTales/ModelingDraft";
var path=folder+"/Corefolder-57-85-ModelingDraft.unity";
if(!AssetDatabase.IsValidFolder(folder))AssetDatabase.CreateFolder("Assets/100BeautiesLab-CharacterVRM/NumberTales","ModelingDraft");
if(AssetDatabase.LoadAssetAtPath<SceneAsset>(path)!=null)throw new System.Exception("Draft review exists; open instead of recreating");
if(!AssetDatabase.CopyAsset("Assets/100BeautiesLab-CharacterVRM/NumberTales/ModelingFoundation/Corefolder-57-85-ModelingFoundation.unity",path))throw new System.Exception("Scene copy failed");
var scene=UnityEditor.SceneManagement.EditorSceneManager.OpenScene(path,UnityEditor.SceneManagement.OpenSceneMode.Single);
foreach(var id in new[]{57,85}) {
    var old=GameObject.Find("Corefolder-"+id+" | common body foundation");
    if(old!=null)UnityEngine.Object.DestroyImmediate(old);
    var modelPath="Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-"+id+"/ModelingDraft";
    var asset=AssetDatabase.LoadAssetAtPath<GameObject>(modelPath+"/Corefolder-"+id+"-Draft.vrm");
    if(asset==null)throw new System.Exception("Missing draft VRM");
    var root=(GameObject)PrefabUtility.InstantiatePrefab(asset,scene);
    root.name="Corefolder-"+id+" | modeling draft";
    foreach(var renderer in root.GetComponentsInChildren<SkinnedMeshRenderer>(true))renderer.updateWhenOffscreen=true;
    PrefabUtility.SaveAsPrefabAsset(root,modelPath+"/Corefolder-"+id+"-Draft.prefab");
    root.transform.position=new Vector3(id==57?-1.4f:1.4f,.03f,0);
    root.transform.rotation=Quaternion.Euler(0,180,0);
    var title=GameObject.Find(id+" title").GetComponent<TextMesh>();
    title.text=id+" | modeling draft\n"+(id==57?"7 tails / armband":"8 tails / pendant")+" | review required";
    title.transform.position=new Vector3(id==57?-1.4f:1.4f,1.5f,-.1f);
    var board=GameObject.Find(id+" official sheet - reference only");board.transform.position=new Vector3(id==57?-1.4f:1.4f,2.55f,.2f);
}
Camera.main.transform.position=new Vector3(0,1.72f,-7);Camera.main.orthographicSize=2.12f;
UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene);AssetDatabase.SaveAssets();
return new{scene=scene.path};
