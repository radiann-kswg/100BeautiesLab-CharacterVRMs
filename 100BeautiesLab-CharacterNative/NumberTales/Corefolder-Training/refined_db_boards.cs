if(EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode)throw new System.Exception("Editor busy");
var scene=UnityEngine.SceneManagement.SceneManager.GetActiveScene();
if(scene.path!="Assets/100BeautiesLab-CharacterVRM/NumberTales/Refined/Corefolder-57-85-Refined.unity")throw new System.Exception("Expected refined scene");
var folder="Assets/100BeautiesLab-CharacterVRM/NumberTales/Refined/DBReferences";
foreach(var id in new[]{57,85}) {
 var generated=GameObject.Find(id+" official sheet - reference only");if(generated!=null)generated.SetActive(false);
 for(int i=0;i<2;i++) {
  var key=i==0?"official":"tails";var file=folder+"/Corefolder-"+id+"-"+key+".png";
  var importer=(TextureImporter)AssetImporter.GetAtPath(file);importer.npotScale=TextureImporterNPOTScale.None;importer.alphaIsTransparency=true;importer.SaveAndReimport();
  var tex=AssetDatabase.LoadAssetAtPath<Texture2D>(file);var matPath=folder+"/Corefolder-"+id+"-"+key+".mat";
  var mat=AssetDatabase.LoadAssetAtPath<Material>(matPath);
  if(mat==null){mat=new Material(Shader.Find("Unlit/Transparent"));AssetDatabase.CreateAsset(mat,matPath);}mat.mainTexture=tex;
  var name=id+" DB "+key;var board=GameObject.Find(name);
  if(board==null){board=GameObject.CreatePrimitive(PrimitiveType.Quad);board.name=name;UnityEngine.Object.DestroyImmediate(board.GetComponent<Collider>());}
  board.GetComponent<Renderer>().sharedMaterial=mat;board.transform.rotation=Quaternion.identity;
  board.transform.position=new Vector3((id==57?-1.4f:1.4f)+(i==0?-.58f:.58f),2.36f,.2f);
  board.transform.localScale=new Vector3(1.08f,1.08f*tex.height/tex.width,1);
 }
 var labelName=id+" DB label";var label=GameObject.Find(labelName);
 if(label==null){label=new GameObject(labelName);var t=label.AddComponent<TextMesh>();t.font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");t.fontSize=48;t.characterSize=.033f;t.anchor=TextAnchor.MiddleCenter;t.color=Color.white;}
 label.GetComponent<TextMesh>().text=id+" | official DB: character + tails";label.transform.position=new Vector3(id==57?-1.4f:1.4f,3.05f,0);
}
Camera.main.transform.position=new Vector3(0,1.5f,-7);Camera.main.orthographicSize=1.72f;
UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene);AssetDatabase.SaveAssets();
return "Official DB boards added; generated sheets retained inactive";
