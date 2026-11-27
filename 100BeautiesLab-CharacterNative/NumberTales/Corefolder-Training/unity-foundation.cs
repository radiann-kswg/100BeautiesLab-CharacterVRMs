if(EditorApplication.isCompiling || EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isUpdating) throw new System.InvalidOperationException("Editor busy");
// Execute this method body with OSS Unity MCP execute_code on codex-training.
// Existing scenes stay open. Run once per review scene; reopening the saved scene needs no rebuild.
var folder = "Assets/100BeautiesLab-CharacterVRM/NumberTales/ModelingFoundation";
if (AssetDatabase.LoadAssetAtPath<SceneAsset>(folder + "/Corefolder-57-85-ModelingFoundation.unity") != null)
    throw new System.InvalidOperationException("Review scene already exists; open it instead.");
if (!AssetDatabase.IsValidFolder(folder))
    AssetDatabase.CreateFolder("Assets/100BeautiesLab-CharacterVRM/NumberTales", "ModelingFoundation");
var current = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
var mode = UnityEditor.SceneManagement.NewSceneMode.Additive;
if (string.IsNullOrEmpty(current.path)) {
    var roots = current.GetRootGameObjects();
    bool pristine = !current.isDirty && roots.Length == 2;
    foreach(var obj in roots) pristine &= obj.GetComponent<Camera>() != null || obj.GetComponent<Light>() != null;
    if (!pristine) throw new System.InvalidOperationException("Preserve the untitled working scene before building review.");
    mode = UnityEditor.SceneManagement.NewSceneMode.Single;
}
var scene = UnityEditor.SceneManagement.EditorSceneManager.NewScene(
    UnityEditor.SceneManagement.NewSceneSetup.DefaultGameObjects,
    mode);
UnityEngine.SceneManagement.SceneManager.SetActiveScene(scene);
Camera camera = null;
foreach(var obj in scene.GetRootGameObjects()) if(obj.GetComponent<Camera>() != null) camera = obj.GetComponent<Camera>();
camera.transform.position = new Vector3(0, 1.6f, -7);
camera.transform.rotation = Quaternion.identity;
camera.orthographic = true;
camera.orthographicSize = 2.05f;
camera.clearFlags = CameraClearFlags.SolidColor;
camera.backgroundColor = new Color(.07f,.08f,.1f);
var results = new System.Collections.Generic.List<object>();
foreach (var id in new[]{57,85}) {
    var path = "Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-"+id+"/ModelingFoundation";
    var asset = AssetDatabase.LoadAssetAtPath<GameObject>(path+"/Corefolder-"+id+"-Foundation.vrm");
    var root = (GameObject)PrefabUtility.InstantiatePrefab(asset, scene);
    root.name = "Corefolder-"+id+" | common body foundation";
    var animator = root.GetComponent<Animator>();
    var expressionChecks = new System.Collections.Generic.List<object>();
    foreach (var renderer in root.GetComponentsInChildren<SkinnedMeshRenderer>(true)) {
        renderer.updateWhenOffscreen = true;
        if (renderer.sharedMesh.blendShapeCount == 0) continue;
        foreach (var key in new[]{"a","EyeClose"}) {
            var index = renderer.sharedMesh.GetBlendShapeIndex(key);
            if (index < 0) throw new System.Exception("Missing expression: " + key);
            var before = new Mesh(); var after = new Mesh();
            var old = renderer.GetBlendShapeWeight(index);
            renderer.SetBlendShapeWeight(index, 0); renderer.BakeMesh(before);
            renderer.SetBlendShapeWeight(index, 100); renderer.BakeMesh(after);
            renderer.SetBlendShapeWeight(index, old);
            var bv=before.vertices; var av=after.vertices; float delta=0;
            for(int j=0;j<bv.Length;j++) delta = Mathf.Max(delta, Vector3.Distance(bv[j],av[j]));
            UnityEngine.Object.DestroyImmediate(before); UnityEngine.Object.DestroyImmediate(after);
            if (delta <= .00001f) throw new System.Exception("Expression has no deformation: " + key);
            expressionChecks.Add(new{key,maxVertexDelta=delta});
        }
    }
    PrefabUtility.SaveAsPrefabAsset(root, path+"/Corefolder-"+id+"-Foundation.prefab");
    float x = id==57 ? -1.4f : 1.4f;
    root.transform.position = new Vector3(x,.05f,0);
    root.transform.rotation = Quaternion.Euler(0,180,0);
    var imagePath = path+"/References/ThreeView-CoreFolder-"+id+".png";
    var ti = (TextureImporter)AssetImporter.GetAtPath(imagePath);
    ti.npotScale = TextureImporterNPOTScale.None; ti.maxTextureSize = 2048;
    ti.textureCompression = TextureImporterCompression.Uncompressed; ti.SaveAndReimport();
    var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(imagePath);
    var board = GameObject.CreatePrimitive(PrimitiveType.Quad);
    board.name = id+" official sheet - reference only";
    UnityEngine.Object.DestroyImmediate(board.GetComponent<Collider>());
    board.transform.position = new Vector3(x,2.4f,.2f);
    board.transform.localScale = new Vector3(2.4f,2.4f*texture.height/texture.width,1);
    var mat = new Material(Shader.Find("Unlit/Texture")); mat.mainTexture=texture;
    AssetDatabase.CreateAsset(mat,path+"/References/ThreeView.mat");
    board.GetComponent<Renderer>().sharedMaterial=mat;
    var title = new GameObject(id+" title").AddComponent<TextMesh>();
    title.text = id+" | modeling foundation\nCommon body / inherited rig and face";
    title.anchor=TextAnchor.MiddleCenter; title.alignment=TextAlignment.Center;
    title.fontSize=48; title.characterSize=.023f;
    title.transform.position=new Vector3(x,1.32f,-.1f);
    results.Add(new{id,avatarValid=animator.avatar.isValid,humanoid=animator.isHuman,expressionChecks});
}
UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene,folder+"/Corefolder-57-85-ModelingFoundation.unity");
AssetDatabase.SaveAssets();
if(SceneView.lastActiveSceneView != null) SceneView.lastActiveSceneView.Frame(new Bounds(new Vector3(0,1.6f,0), new Vector3(5.6f,4.1f,1)),false);
return results;
